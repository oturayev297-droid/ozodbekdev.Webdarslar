"""
Obuna servisi
=============

ASOSIY QOIDA: `Subscription.current_period_end` HECH QACHON jurnalsiz
o'zgarmaydi. Har uzaytirish `SubscriptionPeriod` yozuvi bilan birga,
BITTA tranzaksiyada bo'ladi. Shuning uchun bu faylda
`current_period_end` ni o'zgartiradigan YAGONA funksiya —
`extend_subscription`.
"""

import json
import logging
from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction

from . import dates
from .models import (
    OPEN_STATUSES,
    AdminSetting,
    PaymentMethod,
    PaymentRequest,
    PeriodSource,
    RequestStatus,
    Subscription,
    SubscriptionPeriod,
    SubscriptionPlan,
)

logger = logging.getLogger(__name__)

#: Yagona tarif kodi — hozircha bitta tarif bor
PLAN_CODE = "STUDENT_MONTHLY"

#: Standart oylik narx (tiyinda) — tarif birinchi marta yaratilganda
DEFAULT_PRICE_TIYIN = 10_000_000  # 100 000 so'm

#: Karta rekvizitlari uchun AdminSetting kaliti.
#:
#: BIR NECHTA karta saqlanadi (Humo, Uzcard, Visa) — o'quvchiga hammasi
#: ko'rsatiladi va u o'ziga qulayini tanlaydi. Shuning uchun qiymat JSON
#: massiv: alohida kalitlar bilan bir nechta kartani saqlab bo'lmasdi.
CARDS_KEY = "subscription.cards"

#: Ikki marta bosishdan himoya oynasi (soniya)
DOUBLE_CLICK_WINDOW_SEC = 10


class BillingError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


# ==========================================================================
# Tarif
# ==========================================================================


def get_plan() -> SubscriptionPlan:
    """Amaldagi tarif. Bo'lmasa — standart qiymatlar bilan yaratiladi."""
    plan, created = SubscriptionPlan.objects.get_or_create(
        code=PLAN_CODE,
        defaults={
            'name': "O'quvchi obunasi",
            'price_per_month_tiyin': DEFAULT_PRICE_TIYIN,
        },
    )
    if created:
        logger.info("[OBUNA] Standart tarif yaratildi: %s", plan.code)
    return plan


# ==========================================================================
# Karta rekvizitlari
# ==========================================================================


def _normalize_card(raw):
    """Bitta kartaning maydonlarini tozalaydi. Nomeri bo'sh bo'lsa — karta emas."""
    if not isinstance(raw, dict):
        return None

    def s(key, limit):
        value = raw.get(key)
        return (value.strip()[:limit] if isinstance(value, str) else "")

    number = s('number', 40)
    if not number:
        return None
    return {
        'number': number,
        'holder': s('holder', 80),
        'bank': s('bank', 40),
        'note': s('note', 200),
    }


def get_cards() -> list:
    """Barcha kartalar. Ro'yxat bo'sh bo'lishi mumkin."""
    row = AdminSetting.objects.filter(key=CARDS_KEY).first()
    if not row or not row.value:
        return []
    try:
        parsed = json.loads(row.value)
    except json.JSONDecodeError:
        logger.warning("[OBUNA] Karta ro'yxati o'qilmadi — JSON buzilgan")
        return []
    if not isinstance(parsed, list):
        return []
    return [c for c in (_normalize_card(x) for x in parsed) if c]


#: Karta raqamidagi raqamlar soni. Uzcard va Humo — 16 xona.
#: Yuqori chegara xalqaro kartalar uchun bo'sh qoldirilgan.
CARD_DIGITS = (16, 19)


def update_cards(cards, admin=None) -> list:
    """
    Kartalar ro'yxatini butunlay almashtiradi.

    RAQAM SHU YERDA TEKSHIRILADI. Tekshiruvsiz xato terilgan raqam
    saqlanardi va o'quvchilar pulni yo'q kartaga yuborardi — xato
    faqat "pulim yo'qoldi" degan murojaatdan keyin bilinardi.
    Tekshiruv aynan yozishda: allaqachon saqlangan ro'yxat o'qishda
    jimgina yo'qolib qolmasin.
    """
    if not isinstance(cards, list):
        raise BillingError("Kartalar ro'yxati noto'g'ri")
    if len(cards) > 10:
        raise BillingError("Ko'pi bilan 10 ta karta")

    clean = [c for c in (_normalize_card(x) for x in cards) if c]

    low, high = CARD_DIGITS
    for card in clean:
        digits = ''.join(ch for ch in card['number'] if ch.isdigit())
        if not low <= len(digits) <= high:
            raise BillingError(
                f"Karta raqami noto'g'ri: {card['number']}. "
                f"{low} xonali raqam kiriting."
            )

    AdminSetting.objects.update_or_create(
        key=CARDS_KEY,
        defaults={'value': json.dumps(clean, ensure_ascii=False), 'updated_by': admin},
    )
    logger.info("[OBUNA] Karta ro'yxati yangilandi: %s ta", len(clean))
    return clean


# ==========================================================================
# Obuna yozuvi
# ==========================================================================


def ensure_subscription(user) -> Subscription:
    """
    Obuna yozuvini kerak bo'lganda yaratadi.

    Har foydalanuvchiga oldindan yaratilmaydi: obunasi yo'q oddiy
    foydalanuvchi o'chirilishi mumkin bo'lib qolsin (Subscription.user
    PROTECT bilan bog'langan).
    """
    subscription = Subscription.objects.filter(user=user).first()
    if subscription:
        return subscription
    return Subscription.objects.create(user=user, plan=get_plan())


# ==========================================================================
# Uzaytirish — yagona yo'l
# ==========================================================================


@dataclass
class ExtendResult:
    period: SubscriptionPeriod
    current_period_end: object


@transaction.atomic
def extend_subscription(
    user,
    *,
    source,
    months=None,
    days=None,
    payment_method=None,
    amount_tiyin=None,
    note="",
    admin=None,
    payment_request=None,
) -> ExtendResult:
    """
    Obunani uzaytiradi va jurnalga yozadi.

    Bu `current_period_end` ni o'zgartiradigan YAGONA funksiya. Davr
    yozuvi va sana yangilanishi bitta tranzaksiyada — ikkisi bir-biriga
    to'g'ri kelmay qolishi mumkin emas.
    """
    if months is None and days is None:
        raise BillingError("Oy yoki kun soni ko'rsatilmadi")
    if months is not None and days is not None:
        raise BillingError("Oy va kun birga berilmaydi")

    if months is not None:
        months = int(months)
        if months not in dates.ALLOWED_MONTHS:
            allowed = ", ".join(str(m) for m in dates.ALLOWED_MONTHS)
            raise BillingError(f"Oy soni faqat {allowed} bo'lishi mumkin")
    if days is not None:
        days = int(days)
        if days < 1 or days > 3650:
            raise BillingError("Kun soni 1 dan 3650 gacha bo'lishi kerak")

    plan = get_plan()

    # ── To'lov usuli va summa ──
    # `source` bilan `payment_method` bog'liqligi bazada ham majburiy,
    # lekin bu yerda tushunarli xato matni beramiz.
    if source == PeriodSource.PAYMENT:
        if not payment_method:
            raise BillingError("To'lov usuli tanlanmadi")
        if months is None:
            raise BillingError("To'lov uchun oy soni ko'rsatilishi shart")
        if payment_method not in PaymentMethod.values:
            raise BillingError("To'lov usuli noto'g'ri")

        # Summa SERVERDA hisoblanadi. Admin uni o'zgartira oladi (naqdda
        # chegirma bo'lishi mumkin), lekin oddiy foydalanuvchi emas.
        if amount_tiyin is None:
            amount_tiyin = plan.price_for(months)
        else:
            amount_tiyin = int(amount_tiyin)
            if amount_tiyin < 0:
                raise BillingError("Summa noto'g'ri")
    else:
        # TRIAL / ADMIN_GRANT / MIGRATION — bepul, usul yozilmaydi
        payment_method = None
        amount_tiyin = None

    subscription = ensure_subscription(user)

    # ── Ikki marta bosishdan himoya ──
    # Tugma darhol o'chadi, lekin tarmoq kechikkanda ikkinchi so'rov
    # baribir kelishi mumkin. Bir xil (o'quvchi + muddat + manba) 10
    # soniya ichida takrorlansa — rad etamiz.
    #
    # MUDDAT ham solishtiriladi: "1 kun berish" dan keyin darhol "7 kun"
    # bosilsa, ikkinchisi TAKROR deb rad etilmasligi kerak.
    recent = SubscriptionPeriod.objects.filter(
        subscription=subscription,
        source=source,
        created_at__gte=dates.now() - timedelta(seconds=DOUBLE_CLICK_WINDOW_SEC),
    ).values('months', 'start_date', 'end_date')

    for p in recent:
        if months is not None:
            if p['months'] == months:
                raise BillingError(
                    "Bu uzaytirish hozirgina bajarilgan — ikki marta "
                    "yozilmasligi uchun to'xtatildi.",
                    status=409,
                )
        elif p['months'] is None:
            span = (p['end_date'] - p['start_date']).days
            if span == days:
                raise BillingError(
                    "Bu uzaytirish hozirgina bajarilgan — ikki marta "
                    "yozilmasligi uchun to'xtatildi.",
                    status=409,
                )

    # Qatorni qulflaymiz: bir vaqtda ikki uzaytirish kelsa navbatga tursin
    locked = Subscription.objects.select_for_update().get(pk=subscription.pk)

    # Uzaytirish ESKI tugash sanasidan (agar hali o'tmagan bo'lsa) — erta
    # to'lagan odam qolgan kunlarini yo'qotmaydi.
    start = dates.extension_base(locked.current_period_end)
    end = dates.add_months(start, months) if months is not None else dates.add_days(start, days)

    period = SubscriptionPeriod.objects.create(
        subscription=locked,
        start_date=start,
        end_date=end,
        months=months,
        source=source,
        payment_method=payment_method,
        amount_tiyin=amount_tiyin,
        plan=plan if source == PeriodSource.PAYMENT else None,
        payment_request=payment_request,
        created_by_admin=admin,
        note=(note or "").strip(),
    )

    locked.current_period_end = end
    # Yangi davr ochildi — kutish rejimi qayta ishlatsa bo'ladi
    locked.hold_used_at = None
    # Eslatmalar ham boshidan: 7 -> 3 -> 0 yana ishlaydi
    locked.last_reminder_days_left = None
    locked.save(update_fields=['current_period_end', 'hold_used_at', 'last_reminder_days_left', 'updated_at'])

    logger.info(
        "[OBUNA] %s: +%s (%s%s) -> %s",
        user.username,
        f"{months} oy" if months is not None else f"{days} kun",
        source,
        f"/{payment_method}" if payment_method else "",
        dates.format_date(end),
    )

    return ExtendResult(period=period, current_period_end=end)


def preview_extension(user, months=None, days=None) -> dict:
    """
    Uzaytirish natijasini OLDINDAN hisoblab beradi (hech narsa yozmaydi).

    "Yangi tugash sanasi" shundan olinadi. Klientda hisoblansa, oy oxiri
    va Toshkent kun chegarasi qoidalari ikki joyda takrorlanib,
    ertami-kechmi bir-biriga to'g'ri kelmay qolardi.
    """
    subscription = Subscription.objects.filter(user=user).first()
    plan = get_plan()

    current_end = subscription.current_period_end if subscription else None
    start = dates.extension_base(current_end)
    end = dates.add_months(start, months) if months else dates.add_days(start, days or 0)

    return {
        'current_period_end': current_end,
        'new_period_end': end,
        'amount_tiyin': plan.price_for(months) if months else None,
        'price_per_month_tiyin': plan.price_per_month_tiyin,
    }


def grant_trial(user, admin=None):
    """
    Sinov muddatini beradi — BIR MARTA.

    Avtomatik chaqirilmaydi: bu platformada trial admin qo'lda beradigan
    imkoniyat. Allaqachon davri bo'lganga qayta berilmaydi.
    """
    plan = get_plan()
    if plan.trial_days < 1:
        raise BillingError("Tarifda sinov kunlari 0 — avval uni sozlang")

    subscription = Subscription.objects.filter(user=user).first()
    if subscription and subscription.periods.exists():
        raise BillingError("Bu o'quvchida allaqachon obuna davri bo'lgan")

    return extend_subscription(
        user,
        days=plan.trial_days,
        source=PeriodSource.TRIAL,
        note=f"{plan.trial_days} kunlik sinov muddati",
        admin=admin,
    )


# ==========================================================================
# Holat
# ==========================================================================


@dataclass
class SubscriptionState:
    """Obunaning hisoblangan holati. Bayroq emas — sanadan chiqariladi."""

    status: str  # NONE | TRIAL | ACTIVE | GRACE | HOLD | EXPIRED
    active: bool
    current_period_end: object
    days_left: int
    in_grace: bool
    in_hold: bool
    hold_until: object

    @property
    def end_display(self) -> str:
        return dates.format_date(self.current_period_end)


NONE = 'NONE'
TRIAL = 'TRIAL'
ACTIVE = 'ACTIVE'
GRACE = 'GRACE'
HOLD = 'HOLD'
EXPIRED = 'EXPIRED'

STATUS_LABELS = {
    NONE: "Obuna yo'q",
    TRIAL: "Sinov muddati",
    ACTIVE: "Faol",
    GRACE: "Muhlat berildi",
    HOLD: "Tasdiq kutilmoqda",
    EXPIRED: "Muddati tugagan",
}


def _closed(end, status=EXPIRED) -> SubscriptionState:
    return SubscriptionState(
        status=status,
        active=False,
        current_period_end=end,
        days_left=dates.days_left(end) if end else -1,
        in_grace=False,
        in_hold=False,
        hold_until=None,
    )


def get_state(user, at=None) -> SubscriptionState:
    """
    Foydalanuvchining obuna holatini bazadan o'qiydi.

    BAZADAN O'QIYDI, sessiyadan emas: admin to'lovni tasdiqlagan zahoti
    kirish tiklanishi kerak, foydalanuvchi qayta kirishini kutmasdan.
    Aksi ham: obuna tugasa darhol kuchga kiradi.

    Xatolik bo'lsa — YOPIQ (fail closed).
    """
    at = at or dates.now()

    if not user or not user.is_authenticated:
        return _closed(None, status=NONE)

    # Admin va xodimlar hech qachon cheklanmaydi
    if user.is_staff or user.is_superuser:
        return SubscriptionState(
            status=ACTIVE, active=True, current_period_end=None,
            days_left=9999, in_grace=False, in_hold=False, hold_until=None,
        )

    try:
        subscription = (
            Subscription.objects.select_related('plan').filter(user=user).first()
        )
    except Exception:
        logger.exception("[OBUNA] holatni o'qib bo'lmadi: user=%s", user.pk)
        return _closed(None, status=NONE)

    if subscription is None or subscription.current_period_end is None:
        return _closed(None, status=NONE)

    plan = subscription.plan
    end = subscription.current_period_end
    left = dates.days_left(end, at)
    with_grace = dates.grace_end(end, plan.grace_days)

    if at <= with_grace:
        in_grace = at > end
        if in_grace:
            status = GRACE
        else:
            last = (
                subscription.periods.order_by('-created_at')
                .values_list('source', flat=True)
                .first()
            )
            status = TRIAL if last == PeriodSource.TRIAL else ACTIVE
        return SubscriptionState(
            status=status,
            active=True,
            current_period_end=end,
            days_left=left,
            in_grace=in_grace,
            in_hold=False,
            hold_until=None,
        )

    # ─── KUTISH REJIMI ───
    # Muhlat ham tugadi. Lekin o'quvchi pulni yuborib, tasdiq kutayotgan
    # bo'lishi mumkin — admin qo'lda tasdiqlaydi. Bunday odamni qulflash
    # noto'g'ri bo'lardi: pul ketgan, kirish yopiq.
    #
    # Kutish IKKI shart bilan ishlaydi:
    #   1) hold_used_at qo'yilgan (shu davr uchun "chekni yubordim" bosilgan)
    #   2) hali ham RECEIPT_UPLOADED holatidagi so'rov turibdi
    # Admin rad etsa 2-shart darhol yo'qoladi va qulflanadi.
    #
    # Bu so'rov faqat shu yerda — ya'ni obuna ALLAQACHON yopilgan
    # holatda — bajariladi. Faol obunachi uchun qo'shimcha so'rov yo'q.
    if subscription.hold_used_at:
        hold_until = dates.add_days(subscription.hold_used_at, plan.pending_hold_days)
        if at <= hold_until:
            waiting = PaymentRequest.objects.filter(
                user=user, status=RequestStatus.RECEIPT_UPLOADED
            ).exists()
            if waiting:
                return SubscriptionState(
                    status=HOLD,
                    active=True,
                    current_period_end=end,
                    days_left=left,
                    in_grace=False,
                    in_hold=True,
                    hold_until=hold_until,
                )

    return _closed(end)


def has_active_subscription(user) -> bool:
    return get_state(user).active
