"""
Payme (Paycom) Merchant API
===========================

JSON-RPC 2.0, bitta endpoint. Payme serveri BIZGA murojaat qiladi.

Oqim:
    CheckPerformTransaction  -> to'lov mumkinmi (hech narsa yozilmaydi)
    CreateTransaction        -> tranzaksiya yaratiladi (state 1)
    PerformTransaction       -> pul yechiladi, obuna uzayadi (state 2)
    CancelTransaction        -> bekor (state -1 yoki -2)
    CheckTransaction         -> holatni so'rash
    GetStatement             -> davr bo'yicha ro'yxat (solishtirish uchun)

BIRLIK: summa TIYINDA. Bizning `amount_tiyin` bilan bir xil, aylantirish
kerak emas — bu ataylab: pul birligi ikki joyda o'zgartirilsa xato
muqarrar edi.

VAQT: millisekundlarda (Unix epoch).

IDEMPOTENTLIK IKKI QATLAM:
  1. `GatewayTransaction (provider, external_id)` unique — takror
     `CreateTransaction` ikkinchi yozuv yaratmaydi;
  2. `SubscriptionPeriod.payment_request` unique — takror
     `PerformTransaction` obunani ikki marta uzaytirmaydi.
Payme tarmoq uzilganda so'rovni ATAYLAB qayta yuboradi, shuning uchun
har bir metod takrorlanishga chidamli bo'lishi shart.
"""

import base64
import logging
import secrets
import time
from datetime import datetime
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import GatewayTransaction, PaymentMethod, PaymentRequest, RequestStatus
from ..payment_requests import confirm_request
from ..services import BillingError

logger = logging.getLogger(__name__)

#: Tranzaksiya shuncha vaqt ichida bajarilishi kerak (Payme talabi: 12 soat)
TIMEOUT_MS = 12 * 60 * 60 * 1000


# ==========================================================================
# Xatolar
# ==========================================================================


class PaymeError(Exception):
    """JSON-RPC xatosiga aylanadigan istisno."""

    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


# JSON-RPC standart
ERR_TRANSPORT = -32300        # POST emas
ERR_PARSE = -32700            # JSON o'qilmadi
ERR_INVALID_REQUEST = -32600  # maydonlar yetishmaydi
ERR_METHOD_NOT_FOUND = -32601
ERR_UNAUTHORIZED = -32504     # huquq yetarli emas
ERR_INTERNAL = -32400

# Payme
ERR_INVALID_AMOUNT = -31001
ERR_TRANSACTION_NOT_FOUND = -31003
ERR_CANNOT_CANCEL = -31007
ERR_CANNOT_PERFORM = -31008
ERR_ACCOUNT = -31050          # -31050..-31099 oralig'i account xatolari uchun


def _msg(uz, ru=None, en=None):
    """Payme xato xabarini uch tilda kutadi."""
    return {'uz': uz, 'ru': ru or uz, 'en': en or uz}


# ==========================================================================
# Yordamchilar
# ==========================================================================


def is_configured() -> bool:
    return bool(getattr(settings, 'PAYME_MERCHANT_ID', '') and getattr(settings, 'PAYME_KEY', ''))


def check_auth(header: str) -> bool:
    """
    `Authorization: Basic base64("Paycom:<KEY>")`.

    Doimiy vaqtli solishtirish — kalitni vaqt bo'yicha topib bo'lmasin.
    """
    key = getattr(settings, 'PAYME_KEY', '')
    if not key or not header:
        return False

    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != 'basic':
        return False

    try:
        decoded = base64.b64decode(parts[1], validate=True)
    except Exception:
        return False

    # BAYTLAR bilan solishtiriladi, satrlar bilan EMAS:
    # `secrets.compare_digest` satrlarda faqat ASCII ni qabul qiladi va
    # ASCII bo'lmagan belgida `TypeError` tashlaydi. Buzilgan sarlavha
    # yuborib serverni 500 ga tushirib bo'lardi.
    login, _, password = decoded.partition(b':')
    return (
        secrets.compare_digest(login, b'Paycom')
        and secrets.compare_digest(password, key.encode())
    )


def now_ms() -> int:
    return int(time.time() * 1000)


def to_ms(dt) -> int:
    return int(dt.timestamp() * 1000) if dt else 0


def _account_field() -> str:
    return getattr(settings, 'PAYME_ACCOUNT_FIELD', 'order_id')


def _find_request(account) -> PaymentRequest:
    """
    `account` dan bizning to'lov so'rovimizni topadi.

    Xato kodi -31050 oralig'idan bo'lishi SHART: Payme aynan shu oraliqni
    "foydalanuvchi kiritgan ma'lumot noto'g'ri" deb tushunadi va xabarni
    o'quvchiga ko'rsatadi. Umumiy -32400 bo'lsa "tizim xatosi" deb
    chiqarardi va o'quvchi nima qilishni bilmasdi.
    """
    field = _account_field()
    raw = (account or {}).get(field)

    if raw is None or str(raw).strip() == '':
        raise PaymeError(
            ERR_ACCOUNT,
            _msg("To'lov raqami ko'rsatilmagan", "Не указан номер заказа", "Order id is missing"),
            data=field,
        )

    try:
        request_id = int(raw)
    except (TypeError, ValueError):
        raise PaymeError(
            ERR_ACCOUNT,
            _msg("To'lov raqami noto'g'ri", "Неверный номер заказа", "Invalid order id"),
            data=field,
        )

    payment_request = (
        PaymentRequest.objects.select_related('user', 'plan').filter(pk=request_id).first()
    )
    if payment_request is None:
        raise PaymeError(
            ERR_ACCOUNT,
            _msg("Bunday to'lov topilmadi", "Заказ не найден", "Order not found"),
            data=field,
        )
    return payment_request


def _check_payable(payment_request: PaymentRequest, amount):
    """Summa va holatni tekshiradi. Ikkala yaratish yo'lida ham chaqiriladi."""
    if payment_request.status == RequestStatus.CONFIRMED:
        raise PaymeError(
            ERR_CANNOT_PERFORM,
            _msg("Bu to'lov allaqachon amalga oshirilgan",
                 "Заказ уже оплачен", "Order already paid"),
        )
    if payment_request.status in (RequestStatus.REJECTED, RequestStatus.EXPIRED):
        raise PaymeError(
            ERR_CANNOT_PERFORM,
            _msg("To'lov so'rovi yopilgan", "Заказ закрыт", "Order is closed"),
        )

    try:
        amount = int(amount)
    except (TypeError, ValueError):
        raise PaymeError(ERR_INVALID_AMOUNT, _msg("Summa noto'g'ri", "Неверная сумма", "Invalid amount"))

    # Summa SERVERDAGI qiymat bilan solishtiriladi. Payme yuborgan
    # qiymatga ishonilmaydi.
    if amount != payment_request.amount_tiyin:
        raise PaymeError(
            ERR_INVALID_AMOUNT,
            _msg("Summa mos kelmadi", "Неверная сумма", "Invalid amount"),
        )


# ==========================================================================
# Metodlar
# ==========================================================================


def check_perform_transaction(params):
    payment_request = _find_request(params.get('account'))
    _check_payable(payment_request, params.get('amount'))
    return {'allow': True}


def create_transaction(params):
    external_id = params.get('id')
    if not external_id:
        raise PaymeError(ERR_INVALID_REQUEST, _msg("id ko'rsatilmagan"))

    existing = GatewayTransaction.objects.filter(
        provider=GatewayTransaction.Provider.PAYME, external_id=external_id
    ).first()

    if existing:
        # TAKROR SO'ROV. Payme tarmoq uzilganda qayta yuboradi — bu xato
        # emas, shuning uchun mavjud tranzaksiya ma'lumoti qaytariladi.
        if existing.state != GatewayTransaction.State.CREATED:
            raise PaymeError(
                ERR_CANNOT_PERFORM,
                _msg("Tranzaksiya holati mos emas", "Неверное состояние", "Invalid state"),
            )
        if _is_timed_out(existing):
            _cancel(existing, GatewayTransaction.State.CANCELLED, reason=4)
            raise PaymeError(
                ERR_CANNOT_PERFORM,
                _msg("Tranzaksiya muddati tugadi", "Время истекло", "Transaction timed out"),
            )
        return {
            'create_time': to_ms(existing.created_at),
            'transaction': str(existing.pk),
            'state': existing.state,
        }

    payment_request = _find_request(params.get('account'))
    _check_payable(payment_request, params.get('amount'))

    # Bitta so'rovga BITTA ochiq tranzaksiya. Aks holda o'quvchi ikki
    # marta to'lab yuborishi mumkin edi.
    other_open = GatewayTransaction.objects.filter(
        payment_request=payment_request, state=GatewayTransaction.State.CREATED
    ).first()
    if other_open and not _is_timed_out(other_open):
        raise PaymeError(
            ERR_CANNOT_PERFORM,
            _msg("Bu to'lov uchun boshqa tranzaksiya ochiq",
                 "Есть другая незавершённая транзакция",
                 "Another transaction is pending"),
        )

    try:
        created = GatewayTransaction.objects.create(
            provider=GatewayTransaction.Provider.PAYME,
            external_id=external_id,
            payment_request=payment_request,
            amount_tiyin=int(params['amount']),
            state=GatewayTransaction.State.CREATED,
            external_created_ms=params.get('time'),
            raw_request=params,
        )
    except IntegrityError:
        # Ikkita bir xil so'rov bir vaqtda keldi — bazaning o'zi ushladi
        existing = GatewayTransaction.objects.get(
            provider=GatewayTransaction.Provider.PAYME, external_id=external_id
        )
        return {
            'create_time': to_ms(existing.created_at),
            'transaction': str(existing.pk),
            'state': existing.state,
        }

    logger.info("[PAYME] Tranzaksiya yaratildi: %s (so'rov #%s)", external_id, payment_request.pk)
    return {
        'create_time': to_ms(created.created_at),
        'transaction': str(created.pk),
        'state': created.state,
    }


def perform_transaction(params):
    tx = _get_transaction(params.get('id'))

    if tx.state == GatewayTransaction.State.PERFORMED:
        # TAKROR — allaqachon bajarilgan, o'sha ma'lumot qaytariladi
        return {
            'transaction': str(tx.pk),
            'perform_time': to_ms(tx.performed_at),
            'state': tx.state,
        }

    if tx.state != GatewayTransaction.State.CREATED:
        raise PaymeError(
            ERR_CANNOT_PERFORM,
            _msg("Tranzaksiya bekor qilingan", "Транзакция отменена", "Transaction cancelled"),
        )

    if _is_timed_out(tx):
        _cancel(tx, GatewayTransaction.State.CANCELLED, reason=4)
        raise PaymeError(
            ERR_CANNOT_PERFORM,
            _msg("Tranzaksiya muddati tugadi", "Время истекло", "Transaction timed out"),
        )

    _confirm_subscription(tx, PaymentMethod.PAYME)

    return {
        'transaction': str(tx.pk),
        'perform_time': to_ms(tx.performed_at),
        'state': tx.state,
    }


def cancel_transaction(params):
    tx = _get_transaction(params.get('id'))
    reason = params.get('reason')

    if tx.state == GatewayTransaction.State.CREATED:
        _cancel(tx, GatewayTransaction.State.CANCELLED, reason)

    elif tx.state == GatewayTransaction.State.PERFORMED:
        # TO'LOVDAN KEYIN BEKOR QILISH = pul qaytarish.
        #
        # Obuna davri jurnali O'CHIRILMAYDI — u moliyaviy yozuv va
        # o'zgarmasligi kerak. Buning o'rniga admin xabardor qilinadi va
        # qarorni u qabul qiladi (kunlarni qaytarish yoki qoldirish).
        # Avtomatik o'chirish jurnal bilan obuna sanasini bir-biriga
        # to'g'ri kelmay qolishiga olib kelardi.
        _cancel(tx, GatewayTransaction.State.CANCELLED_AFTER_PERFORM, reason)
        logger.warning(
            "[PAYME] TO'LOVDAN KEYIN BEKOR: tx=%s so'rov=#%s — obuna davri "
            "qo'lda ko'rib chiqilishi kerak",
            tx.external_id, tx.payment_request_id,
        )
        _notify_admins_refund(tx)

    return {
        'transaction': str(tx.pk),
        'cancel_time': to_ms(tx.cancelled_at),
        'state': tx.state,
    }


def check_transaction(params):
    tx = _get_transaction(params.get('id'))
    return {
        'create_time': to_ms(tx.created_at),
        'perform_time': to_ms(tx.performed_at),
        'cancel_time': to_ms(tx.cancelled_at),
        'transaction': str(tx.pk),
        'state': tx.state,
        'reason': tx.cancel_reason,
    }


def get_statement(params):
    """
    Davr bo'yicha tranzaksiyalar. Payme buni o'z yozuvlari bilan
    solishtirish uchun so'raydi — nomuvofiqlik bo'lsa o'zi aniqlaydi.
    """
    try:
        start = int(params['from'])
        end = int(params['to'])
    except (KeyError, TypeError, ValueError):
        raise PaymeError(ERR_INVALID_REQUEST, _msg("from/to noto'g'ri"))

    start_dt = datetime.fromtimestamp(start / 1000, tz=dt_timezone.utc)
    end_dt = datetime.fromtimestamp(end / 1000, tz=dt_timezone.utc)

    rows = (
        GatewayTransaction.objects.filter(
            provider=GatewayTransaction.Provider.PAYME,
            created_at__gte=start_dt,
            created_at__lte=end_dt,
        )
        .select_related('payment_request')
        .order_by('created_at')
    )

    field = _account_field()
    return {
        'transactions': [
            {
                'id': tx.external_id,
                'time': tx.external_created_ms or to_ms(tx.created_at),
                'amount': tx.amount_tiyin,
                'account': {field: str(tx.payment_request_id)},
                'create_time': to_ms(tx.created_at),
                'perform_time': to_ms(tx.performed_at),
                'cancel_time': to_ms(tx.cancelled_at),
                'transaction': str(tx.pk),
                'state': tx.state,
                'reason': tx.cancel_reason,
            }
            for tx in rows
        ]
    }


METHODS = {
    'CheckPerformTransaction': check_perform_transaction,
    'CreateTransaction': create_transaction,
    'PerformTransaction': perform_transaction,
    'CancelTransaction': cancel_transaction,
    'CheckTransaction': check_transaction,
    'GetStatement': get_statement,
}


# ==========================================================================
# Umumiy yordamchilar
# ==========================================================================


def _get_transaction(external_id) -> GatewayTransaction:
    tx = GatewayTransaction.objects.select_related('payment_request').filter(
        provider=GatewayTransaction.Provider.PAYME, external_id=external_id
    ).first()
    if tx is None:
        raise PaymeError(
            ERR_TRANSACTION_NOT_FOUND,
            _msg("Tranzaksiya topilmadi", "Транзакция не найдена", "Transaction not found"),
        )
    return tx


def _is_timed_out(tx: GatewayTransaction) -> bool:
    return (now_ms() - to_ms(tx.created_at)) > TIMEOUT_MS


@transaction.atomic
def _cancel(tx: GatewayTransaction, state, reason=None):
    tx.state = state
    tx.cancelled_at = timezone.now()
    tx.cancel_reason = reason
    tx.save(update_fields=['state', 'cancelled_at', 'cancel_reason'])
    logger.info("[PAYME] Bekor qilindi: %s -> %s (sabab %s)", tx.external_id, state, reason)


def _confirm_subscription(tx: GatewayTransaction, method: str):
    """
    Tranzaksiyani bajarilgan deb belgilaydi va obunani uzaytiradi.

    Obunani uzaytirish `confirm_request` orqali — ya'ni qo'lda tasdiqlash
    bilan AYNAN BIR XIL yo'l. Ikkinchi yo'l yozilsa idempotentlik, narxni
    muzlatish va jurnal qoidalari ikki joyda takrorlanardi.
    """
    with transaction.atomic():
        locked = GatewayTransaction.objects.select_for_update().get(pk=tx.pk)
        if locked.state == GatewayTransaction.State.PERFORMED:
            tx.refresh_from_db()
            return

        locked.state = GatewayTransaction.State.PERFORMED
        locked.performed_at = timezone.now()
        locked.save(update_fields=['state', 'performed_at'])

    try:
        confirm_request(
            locked.payment_request_id,
            admin=None,
            payment_method=method,
            note=f"{method} avtomatik to'lov ({locked.external_id})",
        )
    except BillingError as exc:
        # So'rov allaqachon tasdiqlangan bo'lsa bu XATO EMAS: takror
        # so'rovda shunday bo'ladi va tranzaksiya baribir bajarilgan.
        if exc.status != 409:
            logger.error(
                "[%s] Obunani uzaytirib bo'lmadi (tx=%s): %s",
                method, locked.external_id, exc.message,
            )
            raise

    tx.refresh_from_db()
    logger.info("[%s] To'lov bajarildi: tx=%s so'rov=#%s", method, locked.external_id, locked.payment_request_id)


def _notify_admins_refund(tx: GatewayTransaction):
    from .. import telegram
    from ..dates import format_money

    telegram.send_to_admins(
        f"⚠️ <b>To'lovdan keyin bekor qilindi</b>\n\n"
        f"Tizim: {tx.get_provider_display()}\n"
        f"Tranzaksiya: <code>{tx.external_id}</code>\n"
        f"So'rov: #{tx.payment_request_id}\n"
        f"Summa: {format_money(tx.amount_tiyin)}\n\n"
        f"Obuna davri <b>avtomatik o'chirilmadi</b> — jurnal o'zgarmas. "
        f"Kerak bo'lsa qo'lda ko'rib chiqing."
    )
