"""
Obuna sanalari — Toshkent vaqti bilan
=====================================

NEGA ALOHIDA FAYL: obuna tugash vaqti UTC yarim tunida hisoblansa,
Toshkentda bu ertalab soat 5 bo'ladi — o'quvchi ish kunining boshida
qulflanardi va nima bo'lganini tushunmasdi. Shuning uchun tugash vaqti
HAR DOIM Asia/Tashkent bo'yicha kun oxiriga (23:59:59.999999)
yaxlitlanadi.

SAQLASH — UTC (Django USE_TZ=True). HISOBLASH va KO'RSATISH — Toshkent
vaqtida. Ikkalasi bir joyda aralashmasligi uchun butun hisob shu faylda.
"""

import calendar
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.utils import timezone

UTC = dt_timezone.utc

# O'zbekiston 1996 yildan beri yozgi vaqtga o'tmaydi, lekin offset qo'lda
# yozilmaydi — zoneinfo dan o'qiladi, shunda kelajakda o'zgarsa ham kod
# to'g'ri qoladi.
TASHKENT = ZoneInfo("Asia/Tashkent")

# Oy soni faqat shu qiymatlar bo'lishi mumkin
#: Obuna FAQAT OYLIK.
#:
#: Ilgari (1, 3, 6, 12) edi. Bir oylikka qoldirilgani ataylab:
#: o'quvchi har oy to'laydi va har oy davom etish-etmaslikni qayta hal
#: qiladi. Uzoq muddatli chegirma hozircha yo'q — narx bitta bo'lgani
#: uchun o'quvchi ham, admin ham hisobda adashmaydi.
#:
#: DIQQAT: bu ro'yxat `PaymentRequest` dagi baza cheklovi bilan
#: bog'langan. O'zgartirilsa MIGRATSIYA kerak, aks holda baza eski
#: qiymatlarni talab qilib turaveradi.
ALLOWED_MONTHS = (1,)


def now() -> datetime:
    return timezone.now()


def _to_tashkent(dt: datetime) -> datetime:
    """UTC (yoki boshqa) vaqtni Toshkent mintaqasiga o'tkazadi."""
    if timezone.is_naive(dt):
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(TASHKENT)


def _end_of_day_tashkent(year: int, month: int, day: int) -> datetime:
    """Toshkent bo'yicha berilgan kunning oxiriga to'g'ri keladigan UTC vaqt."""
    local = datetime(year, month, day, 23, 59, 59, 999999, tzinfo=TASHKENT)
    return local.astimezone(UTC)


def end_of_day(dt: datetime) -> datetime:
    """Sanani Asia/Tashkent bo'yicha kun oxiriga yaxlitlaydi."""
    local = _to_tashkent(dt)
    return _end_of_day_tashkent(local.year, local.month, local.day)


def add_months(start: datetime, months: int) -> datetime:
    """
    Toshkent kalendari bo'yicha N oy qo'shadi va kun oxiriga yaxlitlaydi.

    Qisqa oy o'zi to'g'ri hal qilinadi: 31-yanvar + 1 oy = 28 (yoki 29)
    fevral. Qo'lda `month + 1` yozilsa 31-yanvar 3-martga sakrab ketardi.
    """
    local = _to_tashkent(start)

    total = local.month - 1 + months
    year = local.year + total // 12
    month = total % 12 + 1

    # Oyning oxirgi kunidan oshib ketmasin
    day = min(local.day, calendar.monthrange(year, month)[1])

    return _end_of_day_tashkent(year, month, day)


def add_days(start: datetime, days: int) -> datetime:
    """Toshkent bo'yicha N kun qo'shib, kun oxiriga yaxlitlaydi."""
    local = _to_tashkent(start) + timedelta(days=days)
    return _end_of_day_tashkent(local.year, local.month, local.day)


def extension_base(current_period_end, at: datetime = None) -> datetime:
    """
    Uzaytirish qayerdan boshlanadi.

    Obuna hali tugamagan bo'lsa — ESKI tugash sanasidan. Erta to'lagan
    odam qolgan kunlarini yo'qotmasligi kerak, aks holda bu darhol
    shikoyatga aylanadi. Tugagan bo'lsa — hozirgi vaqtdan.
    """
    at = at or now()
    if current_period_end and current_period_end > at:
        return current_period_end
    return at


def grace_end(current_period_end: datetime, grace_days: int) -> datetime:
    """Muhlat (grace) bilan birga oxirgi ishlash vaqti."""
    return add_days(current_period_end, max(0, grace_days))


def days_left(current_period_end, at: datetime = None) -> int:
    """
    Toshkent kunlari bo'yicha necha kun qolgani.
    Bugun tugasa 0, ertaga tugasa 1. Tugagan bo'lsa manfiy.
    """
    if not current_period_end:
        return -1
    at = at or now()
    a = _to_tashkent(at).date()
    b = _to_tashkent(current_period_end).date()
    return (b - a).days


def format_date(dt) -> str:
    """Ko'rsatish uchun: "02.08.2026" (Toshkent kuni)."""
    if not dt:
        return "—"
    local = _to_tashkent(dt)
    return f"{local.day:02d}.{local.month:02d}.{local.year}"


# --------------------------------------------------------------------------
# Pul
# --------------------------------------------------------------------------
#
# Narxlar TIYINDA, butun son sifatida saqlanadi. Kasrli son ATAYLAB
# ishlatilmaydi: 0.1 + 0.2 != 0.3, va pul hisobida bu xato yig'ilib boradi.


def tiyin_to_soum(tiyin) -> int:
    if tiyin is None:
        return 0
    return round(tiyin / 100)


def format_money(tiyin) -> str:
    """10_000_000 tiyin -> "100 000 so'm"."""
    if tiyin is None:
        return "—"
    return f"{tiyin_to_soum(tiyin):,}".replace(",", " ") + " so'm"
