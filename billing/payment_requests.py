"""
To'lov so'rovi oqimi
====================

  o'quvchi so'rov yuboradi     -> REQUESTED
  admin kartani beradi         -> CARD_ISSUED
  o'quvchi "chekni yubordim"   -> RECEIPT_UPLOADED  (kutish rejimi yoqiladi)
  admin tasdiqlaydi            -> CONFIRMED         (davr yaratiladi)
  admin rad etadi              -> REJECTED          (kutish darhol tugaydi)
  javobsiz qoladi              -> EXPIRED

KARTA REKVIZITLARI hech qachon ommaviy sahifada qaytmaydi. Yagona yo'l —
o'quvchining O'ZIDA CARD_ISSUED holatidagi so'rov bo'lishi.
"""

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction

from . import dates, telegram
from .models import (
    OPEN_STATUSES,
    PaymentMethod,
    PaymentRequest,
    PeriodSource,
    ReceiptSource,
    RequestStatus,
    Subscription,
)
from .services import (
    BillingError,
    ensure_subscription,
    extend_subscription,
    get_cards,
    get_plan,
)

logger = logging.getLogger(__name__)

#: Javobsiz so'rov shuncha kundan keyin kuyadi
REQUEST_TTL_DAYS = 7


# ==========================================================================
# O'QUVCHI TOMONI
# ==========================================================================


def get_open_request(user):
    """O'quvchining ochiq so'rovi (bo'lmasa None)."""
    return (
        PaymentRequest.objects.filter(user=user, status__in=OPEN_STATUSES)
        .order_by('-requested_at')
        .first()
    )


@transaction.atomic
def create_request(user, months) -> PaymentRequest:
    try:
        months = int(months)
    except (TypeError, ValueError):
        raise BillingError("Muddat noto'g'ri")

    if months not in dates.ALLOWED_MONTHS:
        allowed = ", ".join(str(m) for m in dates.ALLOWED_MONTHS)
        raise BillingError(f"Muddat faqat {allowed} oy bo'ladi")

    if get_open_request(user):
        raise BillingError(
            "Sizda javobi kutilayotgan so'rov bor. Avval u yakunlanishi kerak.",
            status=409,
        )

    plan = get_plan()
    ensure_subscription(user)

    # SUMMA SERVERDA HISOBLANADI. Klientdan kelgan qiymat umuman
    # o'qilmaydi — aks holda o'quvchi o'zi istagan summani yozib yuborardi.
    amount_tiyin = plan.price_for(months)

    try:
        created = PaymentRequest.objects.create(
            user=user,
            plan=plan,
            months=months,
            amount_tiyin=amount_tiyin,
            expires_at=dates.now() + timedelta(days=REQUEST_TTL_DAYS),
        )
    except IntegrityError:
        # Qisman unique indeks — ikkita so'rov bir vaqtda kelgan hol
        raise BillingError("Sizda javobi kutilayotgan so'rov bor.", status=409)

    logger.info(
        "[OBUNA] %s: to'lov so'rovi #%s (%s oy, %s tiyin)",
        user.username, created.pk, months, amount_tiyin,
    )

    # Xabarnoma asosiy amalni YIQITMAYDI: telegram.py hech qachon xato
    # tashlamaydi, lekin tranzaksiya commit bo'lgandan keyin yuborilishi
    # kerak — aks holda rollback bo'lsa mavjud bo'lmagan so'rov haqida
    # xabar ketardi.
    transaction.on_commit(lambda: telegram.notify_request_created(created))

    return created


def get_card_for_user(user) -> dict:
    """
    Karta rekvizitlarini qaytaradi — FAQAT so'rovi CARD_ISSUED
    holatida bo'lgan o'quvchiga.
    """
    open_request = (
        PaymentRequest.objects.filter(user=user, status=RequestStatus.CARD_ISSUED)
        .order_by('-requested_at')
        .first()
    )
    if not open_request:
        raise BillingError(
            "Karta rekvizitlari hali berilmagan. Administrator so'rovingizni "
            "ko'rib chiqmoqda.",
            status=403,
        )
    # Bir nechta karta bo'lishi mumkin — o'quvchi o'ziga qulayini tanlaydi
    return {'request': open_request, 'cards': get_cards()}


@transaction.atomic
def mark_receipt_sent(user, source=None) -> PaymentRequest:
    """O'quvchi "chekni yubordim" tugmasini bosdi — kutish rejimi yoqiladi."""
    source = str(source or ReceiptSource.OTHER).upper()
    if source not in ReceiptSource.values:
        source = ReceiptSource.OTHER

    open_request = (
        PaymentRequest.objects.select_for_update()
        .filter(user=user, status__in=[RequestStatus.REQUESTED, RequestStatus.CARD_ISSUED])
        .order_by('-requested_at')
        .first()
    )
    if not open_request:
        raise BillingError("Ochiq to'lov so'rovi topilmadi", status=404)

    open_request.status = RequestStatus.RECEIPT_UPLOADED
    open_request.receipt_sent_at = dates.now()
    open_request.receipt_source = source
    open_request.save(update_fields=['status', 'receipt_sent_at', 'receipt_source', 'updated_at'])

    # ── KUTISH REJIMI ──
    # Muhlat qisqa, tasdiqlash esa qo'lda. Pulni yuborib javob kutayotgan
    # odam qulflanib qolmasligi kerak.
    #
    # BIR DAVRDA BIR MARTA: `hold_used_at` faqat hali qo'yilmagan bo'lsa
    # yoziladi. Rad etilib, qayta yuborilsa — muddat eskisidan
    # hisoblanaveradi, ya'ni cheksiz uzaytirib bo'lmaydi.
    subscription = Subscription.objects.select_for_update().filter(user=user).first()
    if subscription and not subscription.hold_used_at:
        subscription.hold_used_at = dates.now()
        subscription.save(update_fields=['hold_used_at', 'updated_at'])

    logger.info(
        "[OBUNA] To'lov so'rovi #%s: chek yuborildi (%s), kutish rejimi",
        open_request.pk, source,
    )

    hold_days = get_plan().pending_hold_days
    transaction.on_commit(
        lambda: telegram.notify_receipt_sent(open_request, hold_days)
    )

    return open_request


# ==========================================================================
# ADMIN TOMONI
# ==========================================================================


@transaction.atomic
def issue_card(request_id, admin) -> PaymentRequest:
    req = PaymentRequest.objects.select_for_update().filter(pk=request_id).first()
    if not req:
        raise BillingError("So'rov topilmadi", status=404)
    if req.status != RequestStatus.REQUESTED:
        raise BillingError(
            f"Bu so'rov \"{req.get_status_display()}\" holatida — "
            "kartani faqat yangi so'rovga berish mumkin",
            status=409,
        )

    req.status = RequestStatus.CARD_ISSUED
    req.card_issued_at = dates.now()
    req.reviewed_by_admin = admin
    req.save(update_fields=['status', 'card_issued_at', 'reviewed_by_admin', 'updated_at'])

    logger.info("[OBUNA] So'rov #%s: karta berildi (admin=%s)", req.pk, admin)

    cards = get_cards()
    transaction.on_commit(lambda: telegram.notify_card_issued(req, cards))

    return req


def confirm_request(request_id, admin, payment_method=None, amount_tiyin=None, note=""):
    """
    So'rovni tasdiqlaydi va obunani uzaytiradi.

    IDEMPOTENT: davr yozuvida `payment_request` unique. Tugma ikki marta
    bosilsa ikkinchisi bazada rad etiladi — obuna ikki marta uzaymaydi.
    """
    with transaction.atomic():
        req = PaymentRequest.objects.select_for_update().filter(pk=request_id).first()
        if not req:
            raise BillingError("So'rov topilmadi", status=404)

        if req.status == RequestStatus.CONFIRMED or hasattr(req, 'period'):
            raise BillingError("Bu so'rov allaqachon tasdiqlangan", status=409)
        if req.status not in OPEN_STATUSES:
            raise BillingError(
                f"\"{req.get_status_display()}\" holatidagi so'rovni tasdiqlab bo'lmaydi",
                status=409,
            )

        method = str(payment_method or PaymentMethod.CARD_TRANSFER).upper()
        if method not in PaymentMethod.values:
            raise BillingError("To'lov usuli noto'g'ri")

        result = extend_subscription(
            req.user,
            months=req.months,
            source=PeriodSource.PAYMENT,
            payment_method=method,
            amount_tiyin=req.amount_tiyin if amount_tiyin is None else amount_tiyin,
            note=note,
            admin=admin,
            payment_request=req,
        )

        req.status = RequestStatus.CONFIRMED
        req.confirmed_at = dates.now()
        req.reviewed_by_admin = admin
        req.save(update_fields=['status', 'confirmed_at', 'reviewed_by_admin', 'updated_at'])

    logger.info("[OBUNA] So'rov #%s tasdiqlandi (admin=%s)", request_id, admin)

    telegram.notify_confirmed(
        req.user, req.months, result.period.amount_tiyin, result.current_period_end
    )

    return result


@transaction.atomic
def reject_request(request_id, admin, reason) -> PaymentRequest:
    note = (reason or "").strip()
    if not note:
        raise BillingError("Rad etish sababi yozilishi shart")

    req = PaymentRequest.objects.select_for_update().filter(pk=request_id).first()
    if not req:
        raise BillingError("So'rov topilmadi", status=404)
    if req.status not in OPEN_STATUSES:
        raise BillingError(
            f"\"{req.get_status_display()}\" holatidagi so'rovni rad etib bo'lmaydi",
            status=409,
        )

    # Kutish rejimi shu bilan DARHOL tugaydi: holat endi RECEIPT_UPLOADED
    # emas, darvoza esa aynan shu holatni qidiradi.
    req.status = RequestStatus.REJECTED
    req.rejected_at = dates.now()
    req.reviewed_by_admin = admin
    req.admin_note = note
    req.save(update_fields=['status', 'rejected_at', 'reviewed_by_admin', 'admin_note', 'updated_at'])

    logger.info("[OBUNA] So'rov #%s rad etildi (admin=%s): %s", req.pk, admin, note)

    transaction.on_commit(lambda: telegram.notify_rejected(req.user, note))

    return req


def expire_stale_requests() -> int:
    """
    Javobsiz qolgan so'rovlarni kuydiradi.

    FAQAT `REQUESTED` va `CARD_ISSUED`. `RECEIPT_UPLOADED` hech qachon
    avtomatik kuymaydi — o'quvchi pulni yuborib, tasdiq kutib turganda
    so'rovi yo'qolsa, pul ketgan bo'lardi. Uni faqat admin yopadi.
    """
    count = PaymentRequest.objects.filter(
        status__in=[RequestStatus.REQUESTED, RequestStatus.CARD_ISSUED],
        expires_at__lt=dates.now(),
    ).update(status=RequestStatus.EXPIRED)

    if count:
        logger.info("[OBUNA] %s ta javobsiz so'rov kuydirildi", count)
    return count
