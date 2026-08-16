"""
Click SHOP API
==============

Ikkita endpoint, Click serveri BIZGA murojaat qiladi:

    /prepare   (action=0)  -> to'lovni tekshirish va band qilish
    /complete  (action=1)  -> pul yechildi, obunani uzaytiramiz

IMZO (rasmiy click-integration-php kutubxonasidan):

    md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id
        + (action == 1 ? merchant_prepare_id : "") + amount + action + sign_time)

BIRLIK — DIQQAT: Click summani **SO'MDA**, kasrli son sifatida yuboradi
(masalan `99000.00`). Payme esa tiyinda. Shu farq ikkita alohida modul
bo'lishining asosiy sababi: bitta joyda aralashtirilsa 100 barobar xato
qilingan to'lov qabul qilinardi.

XATO KODLARI (rasmiy kutubxonadan):
     0  Muvaffaqiyatli
    -1  Imzo noto'g'ri
    -2  Summa noto'g'ri
    -3  Action topilmadi
    -4  Allaqachon to'langan
    -5  Foydalanuvchi topilmadi
    -6  Tranzaksiya topilmadi
    -8  So'rovda xato (maydonlar yetishmaydi)
    -9  Tranzaksiya bekor qilingan
"""

import hashlib
import logging
import secrets
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import GatewayTransaction, PaymentMethod, PaymentRequest, RequestStatus
from ..payment_requests import confirm_request
from ..services import BillingError

logger = logging.getLogger(__name__)

# Xato kodlari
OK = 0
ERR_SIGN = -1
ERR_AMOUNT = -2
ERR_ACTION = -3
ERR_ALREADY_PAID = -4
ERR_USER_NOT_FOUND = -5
ERR_TX_NOT_FOUND = -6
ERR_BAD_REQUEST = -8
ERR_CANCELLED = -9

NOTES = {
    OK: "Success",
    ERR_SIGN: "SIGN CHECK FAILED!",
    ERR_AMOUNT: "Incorrect parameter amount",
    ERR_ACTION: "Action not found",
    ERR_ALREADY_PAID: "Already paid",
    ERR_USER_NOT_FOUND: "User does not exist",
    ERR_TX_NOT_FOUND: "Transaction does not exist",
    ERR_BAD_REQUEST: "Error in request from click",
    ERR_CANCELLED: "Transaction cancelled",
}

ACTION_PREPARE = 0
ACTION_COMPLETE = 1

#: Kasrli summani solishtirishdagi ruxsat etilgan farq (so'm).
#: Rasmiy kutubxonada ham 0.01 ishlatiladi.
AMOUNT_TOLERANCE = Decimal('0.01')

REQUIRED_FIELDS = (
    'click_trans_id', 'service_id', 'click_paydoc_id', 'merchant_trans_id',
    'amount', 'action', 'error', 'error_note', 'sign_time', 'sign_string',
)


class ClickResult(Exception):
    """Javob sifatida qaytariladigan xato."""

    def __init__(self, code):
        super().__init__(NOTES.get(code, 'Error'))
        self.code = code
        self.note = NOTES.get(code, 'Error')


def is_configured() -> bool:
    return bool(
        getattr(settings, 'CLICK_SERVICE_ID', '')
        and getattr(settings, 'CLICK_SECRET_KEY', '')
    )


# ==========================================================================
# Imzo
# ==========================================================================


def build_sign(data: dict) -> str:
    """
    Imzoni hisoblaydi.

    Maydonlar SATR sifatida, kelgan ko'rinishida qo'shiladi — raqamga
    aylantirilmaydi. Click `amount` ni `99000.00` deb yuborsa, imzo ham
    aynan shu satrdan hisoblangan; uni `99000` ga aylantirsak imzo
    mos kelmay qolardi.
    """
    action = str(data.get('action', ''))
    parts = [
        str(data.get('click_trans_id', '')),
        str(data.get('service_id', '')),
        getattr(settings, 'CLICK_SECRET_KEY', ''),
        str(data.get('merchant_trans_id', '')),
        str(data.get('merchant_prepare_id', '')) if action == str(ACTION_COMPLETE) else '',
        str(data.get('amount', '')),
        action,
        str(data.get('sign_time', '')),
    ]
    return hashlib.md5(''.join(parts).encode()).hexdigest()


def check_sign(data: dict) -> bool:
    """Doimiy vaqtli solishtirish — imzoni bayt-bayt topib bo'lmasin."""
    given = str(data.get('sign_string', ''))
    return secrets.compare_digest(build_sign(data), given)


# ==========================================================================
# Tekshiruvlar
# ==========================================================================


def _validate(data: dict, action: int):
    """Rasmiy kutubxonadagi `request_check` bilan bir xil tartib."""
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing or (action == ACTION_COMPLETE and 'merchant_prepare_id' not in data):
        logger.warning("[CLICK] So'rovda maydon yetishmaydi: %s", missing)
        raise ClickResult(ERR_BAD_REQUEST)

    # IMZO BIRINCHI: imzosiz so'rovga qarab hech qanday ma'lumot
    # oshkor qilinmasligi kerak (mavjud/mavjud emas farqi ham).
    if not check_sign(data):
        logger.warning("[CLICK] Imzo mos kelmadi: trans=%s", data.get('click_trans_id'))
        raise ClickResult(ERR_SIGN)

    if str(data.get('service_id')) != str(getattr(settings, 'CLICK_SERVICE_ID', '')):
        raise ClickResult(ERR_SIGN)

    if action not in (ACTION_PREPARE, ACTION_COMPLETE):
        raise ClickResult(ERR_ACTION)


def _find_request(data: dict) -> PaymentRequest:
    try:
        request_id = int(data.get('merchant_trans_id'))
    except (TypeError, ValueError):
        raise ClickResult(ERR_USER_NOT_FOUND)

    payment_request = PaymentRequest.objects.select_related('user').filter(pk=request_id).first()
    if payment_request is None:
        raise ClickResult(ERR_USER_NOT_FOUND)
    return payment_request


def _check_state(payment_request: PaymentRequest):
    if payment_request.status == RequestStatus.CONFIRMED:
        raise ClickResult(ERR_ALREADY_PAID)
    if payment_request.status in (RequestStatus.REJECTED, RequestStatus.EXPIRED):
        raise ClickResult(ERR_CANCELLED)


def _check_amount(payment_request: PaymentRequest, raw_amount) -> int:
    """
    Click SO'MDA yuboradi. Tiyinga aylantirib, serverdagi qiymat bilan
    solishtiramiz — klientdan kelgan summaga ishonilmaydi.
    """
    try:
        soum = Decimal(str(raw_amount))
    except (InvalidOperation, TypeError, ValueError):
        raise ClickResult(ERR_AMOUNT)

    expected = Decimal(payment_request.amount_tiyin) / 100
    if abs(soum - expected) > AMOUNT_TOLERANCE:
        logger.warning(
            "[CLICK] Summa mos kelmadi: kelgan=%s kutilgan=%s (so'rov #%s)",
            soum, expected, payment_request.pk,
        )
        raise ClickResult(ERR_AMOUNT)

    return int(soum * 100)


# ==========================================================================
# Endpointlar
# ==========================================================================


def prepare(data: dict) -> dict:
    """
    `action=0`. To'lovni tekshiradi va tranzaksiya yozuvini ochadi.

    `merchant_prepare_id` sifatida BIZNING `GatewayTransaction.pk`
    qaytariladi — Click uni `complete` da qaytarib yuboradi va shu bilan
    ikki chaqiruv bog'lanadi.
    """
    _validate(data, ACTION_PREPARE)
    payment_request = _find_request(data)
    _check_state(payment_request)
    amount_tiyin = _check_amount(payment_request, data.get('amount'))

    external_id = str(data.get('click_trans_id'))

    existing = GatewayTransaction.objects.filter(
        provider=GatewayTransaction.Provider.CLICK, external_id=external_id
    ).first()

    if existing:
        # TAKROR `prepare` — Click tarmoq uzilganda qayta yuboradi
        if existing.state == GatewayTransaction.State.PERFORMED:
            raise ClickResult(ERR_ALREADY_PAID)
        if existing.state != GatewayTransaction.State.CREATED:
            raise ClickResult(ERR_CANCELLED)
        tx = existing
    else:
        try:
            tx = GatewayTransaction.objects.create(
                provider=GatewayTransaction.Provider.CLICK,
                external_id=external_id,
                payment_request=payment_request,
                amount_tiyin=amount_tiyin,
                state=GatewayTransaction.State.CREATED,
                raw_request=data,
            )
        except IntegrityError:
            tx = GatewayTransaction.objects.get(
                provider=GatewayTransaction.Provider.CLICK, external_id=external_id
            )

    logger.info("[CLICK] prepare: trans=%s so'rov=#%s", external_id, payment_request.pk)

    return {
        'click_trans_id': data.get('click_trans_id'),
        'merchant_trans_id': data.get('merchant_trans_id'),
        'merchant_prepare_id': tx.pk,
        'error': OK,
        'error_note': NOTES[OK],
    }


def complete(data: dict) -> dict:
    """`action=1`. Pul yechilgan — obunani uzaytiramiz."""
    _validate(data, ACTION_COMPLETE)
    payment_request = _find_request(data)

    try:
        prepare_id = int(data.get('merchant_prepare_id'))
    except (TypeError, ValueError):
        raise ClickResult(ERR_TX_NOT_FOUND)

    tx = GatewayTransaction.objects.select_related('payment_request').filter(
        pk=prepare_id,
        provider=GatewayTransaction.Provider.CLICK,
        payment_request=payment_request,
    ).first()
    if tx is None:
        raise ClickResult(ERR_TX_NOT_FOUND)

    _check_amount(payment_request, data.get('amount'))

    # CLICK O'ZI XATO YUBORISHI MUMKIN: `error < 0` bo'lsa pul yechilmagan.
    # Bunda bandlikni bekor qilamiz va -9 qaytaramiz (rasmiy kutubxonadagi
    # kabi) — aks holda to'lanmagan obuna ochilib ketardi.
    try:
        click_error = int(data.get('error', 0))
    except (TypeError, ValueError):
        click_error = 0

    if click_error < 0:
        if tx.is_open:
            tx.state = GatewayTransaction.State.CANCELLED
            tx.cancelled_at = timezone.now()
            tx.cancel_reason = click_error
            tx.save(update_fields=['state', 'cancelled_at', 'cancel_reason'])
        logger.warning("[CLICK] Click xato yubordi: %s (trans=%s)", click_error, tx.external_id)
        raise ClickResult(ERR_CANCELLED)

    if tx.state == GatewayTransaction.State.PERFORMED:
        raise ClickResult(ERR_ALREADY_PAID)
    if tx.state != GatewayTransaction.State.CREATED:
        raise ClickResult(ERR_CANCELLED)

    _perform(tx)

    logger.info("[CLICK] complete: trans=%s so'rov=#%s", tx.external_id, payment_request.pk)

    return {
        'click_trans_id': data.get('click_trans_id'),
        'merchant_trans_id': data.get('merchant_trans_id'),
        'merchant_confirm_id': tx.pk,
        'error': OK,
        'error_note': NOTES[OK],
    }


def _perform(tx: GatewayTransaction):
    """
    Tranzaksiyani bajarilgan deb belgilaydi va obunani uzaytiradi.

    Payme dagi bilan bir xil naqsh: obunani uzaytirish YAGONA yo'l —
    `confirm_request`, ya'ni qo'lda tasdiqlash bilan aynan bir xil.
    """
    with transaction.atomic():
        locked = GatewayTransaction.objects.select_for_update().get(pk=tx.pk)
        if locked.state == GatewayTransaction.State.PERFORMED:
            return
        locked.state = GatewayTransaction.State.PERFORMED
        locked.performed_at = timezone.now()
        locked.save(update_fields=['state', 'performed_at'])

    try:
        confirm_request(
            locked.payment_request_id,
            admin=None,
            payment_method=PaymentMethod.CLICK,
            note=f"Click avtomatik to'lov ({locked.external_id})",
        )
    except BillingError as exc:
        # 409 = allaqachon tasdiqlangan. Takror so'rovda normal hol.
        if exc.status != 409:
            logger.error(
                "[CLICK] Obunani uzaytirib bo'lmadi (trans=%s): %s",
                locked.external_id, exc.message,
            )
            raise

    tx.refresh_from_db()


def error_response(data: dict, code: int) -> dict:
    """Xato javobi. Click `error` va `error_note` maydonlarini kutadi."""
    return {
        'click_trans_id': data.get('click_trans_id'),
        'merchant_trans_id': data.get('merchant_trans_id'),
        'error': code,
        'error_note': NOTES.get(code, 'Error'),
    }
