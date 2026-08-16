"""
Login urinishlarini cheklash
============================

NEGA KERAK: parol validatsiyasi kuchli parol talab qiladi, lekin bu
brute-force dan himoya QILMAYDI. Cheklovsiz hujumchi soatda minglab
parolni sinab ko'ra oladi, ayniqsa foydalanuvchi nomlari oshkor bo'lsa
(admin panelda "Yangi o'quvchilar" ro'yxati bor).

NEGA CACHE EMAS, BAZA: standart `LocMemCache` har bir jarayonda alohida.
Gunicorn 3 worker bilan ishlaganda hujumchi 3 barobar ko'p urinish olardi,
server restart bo'lsa hisoblagich nolga tushardi. Baza hammasi uchun bitta.

QULFLASH MANTIG'I — sirg'aluvchi oyna:
  * oxirgi WINDOW ichidagi muvaffaqiyatsiz urinishlar sanaladi;
  * MAX ga yetsa, OXIRGI urinishdan COOLDOWN o'tguncha qulflanadi;
  * qulf davomida yangi urinish YOZILMAYDI — aks holda hujumchi o'zi
    urinib turib qulfni cheksiz uzaytirardi va qulf hech qachon
    ochilmasdi (foydalanuvchining o'zi ham kira olmasdi).

IKKI DARAJA:
  * foydalanuvchi nomi bo'yicha — bitta hisobga qaratilgan hujum;
  * IP bo'yicha — turli nomlarni ketma-ket sinash (parol purkash).

ANTI-ENUMERATSIYA: qulflangan javob foydalanuvchi mavjudligini oshkor
qilmaydi. Mavjud bo'lmagan nom ham xuddi shunday qulflanadi.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from .models import LoginAttempt

logger = logging.getLogger(__name__)

#: Urinishlar shu oyna ichida sanaladi
WINDOW = timedelta(minutes=15)

#: Qulf oxirgi urinishdan keyin shuncha vaqt turadi
COOLDOWN = timedelta(minutes=15)

#: Bitta foydalanuvchi nomiga nechta xato urinish
MAX_PER_USERNAME = 5

#: Bitta IP dan nechta xato urinish (turli nomlar bilan ham)
MAX_PER_IP = 20

#: Parolni tiklash so'rovi: bitta IP dan oynada nechta marta.
#: Kod so'rovining o'zi "xato" emas, lekin cheklovsiz bu email spam
#: vositasiga aylanardi — begonaning pochtasiga o'nlab xat yuborib bo'lardi.
MAX_RESET_PER_IP = 5

#: Yozuvlar shundan keyin keraksiz — `prune_login_attempts` o'chiradi
RETENTION = timedelta(days=30)


def client_ip(request):
    """
    So'rov kelgan IP.

    `X-Forwarded-For` ni ISHONCH BILAN o'qib bo'lmaydi — uni klient o'zi
    yozib yuborishi mumkin. nginx `$proxy_add_x_forwarded_for` bilan
    O'ZI ko'rgan manzilni ro'yxatning OXIRIGA qo'shadi, shuning uchun
    ishonchli qiymat — eng oxirgi element. Chapdagilar klientdan kelgan
    va soxta bo'lishi mumkin.

    Bu bitta ishonchli proksi (nginx) borligini nazarda tutadi —
    DEPLOY.md dagi konfiguratsiya aynan shunday.
    """
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        parts = [p.strip() for p in forwarded.split(',') if p.strip()]
        if parts:
            return parts[-1]
    return request.META.get('REMOTE_ADDR') or None


def _failures(since, purpose=LoginAttempt.Purpose.LOGIN, **filters):
    return LoginAttempt.objects.filter(
        purpose=purpose, successful=False, created_at__gte=since, **filters
    )


def check_locked(username, ip):
    """
    Qulflanganmi tekshiradi.

    Qaytaradi: `(locked: bool, retry_after_seconds: int, reason: str|None)`
    """
    now = timezone.now()
    since = now - WINDOW

    checks = []
    if username:
        checks.append(('username', _failures(since, username__iexact=username), MAX_PER_USERNAME))
    if ip:
        checks.append(('ip', _failures(since, ip=ip), MAX_PER_IP))

    worst_seconds = 0
    reason = None

    for label, queryset, limit in checks:
        count = queryset.count()
        if count < limit:
            continue
        last = queryset.order_by('-created_at').values_list('created_at', flat=True).first()
        if not last:
            continue
        unlock_at = last + COOLDOWN
        if now < unlock_at:
            seconds = int((unlock_at - now).total_seconds())
            if seconds > worst_seconds:
                worst_seconds = seconds
                reason = label

    return (worst_seconds > 0), worst_seconds, reason


def record_failure(request, username):
    """Muvaffaqiyatsiz urinishni yozadi."""
    attempt = LoginAttempt.objects.create(
        username=(username or '')[:150],
        ip=client_ip(request),
        successful=False,
        purpose=LoginAttempt.Purpose.LOGIN,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
    )
    logger.warning(
        "[AUTH] Muvaffaqiyatsiz login: username=%s ip=%s", attempt.username, attempt.ip
    )
    return attempt


def record_success(request, user):
    """
    Muvaffaqiyatli kirishni yozadi va shu nom bo'yicha xatolarni tozalaydi.

    IP bo'yicha xatolar QOLADI: bir muvaffaqiyatli kirish bilan IP
    cheklovini nolga tushirib bo'lmasligi kerak — aks holda hujumchi
    o'zining haqiqiy hisobiga kirib, hisoblagichni tozalab, hujumni
    davom ettirardi.
    """
    LoginAttempt.objects.create(
        username=user.username[:150],
        ip=client_ip(request),
        successful=True,
        purpose=LoginAttempt.Purpose.LOGIN,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
    )
    LoginAttempt.objects.filter(
        purpose=LoginAttempt.Purpose.LOGIN,
        username__iexact=user.username,
        successful=False,
    ).delete()


def lockout_message(seconds) -> str:
    """Foydalanuvchiga ko'rsatiladigan matn. Sabab oshkor qilinmaydi."""
    minutes = max(1, round(seconds / 60))
    return (
        f"Juda ko'p muvaffaqiyatsiz urinish. Xavfsizlik uchun kirish "
        f"vaqtincha to'xtatildi — {minutes} daqiqadan keyin qayta urinib "
        f"ko'ring. Parolni unutgan bo'lsangiz, uni tiklashingiz mumkin."
    )


def prune_old(now=None) -> int:
    """Eski yozuvlarni o'chiradi (jadval cheksiz o'smasin)."""
    now = now or timezone.now()
    count, _ = LoginAttempt.objects.filter(created_at__lt=now - RETENTION).delete()
    return count


# --------------------------------------------------------------------------
# Parolni tiklash so'rovini cheklash
# --------------------------------------------------------------------------


def check_reset_throttle(ip):
    """
    Bitta IP dan juda ko'p tiklash kodi so'ralganini tekshiradi.

    Qaytaradi: `(throttled: bool, retry_after_seconds: int)`
    """
    if not ip:
        return False, 0

    now = timezone.now()
    attempts = _failures(now - WINDOW, purpose=LoginAttempt.Purpose.RESET, ip=ip)

    if attempts.count() < MAX_RESET_PER_IP:
        return False, 0

    last = attempts.order_by('-created_at').values_list('created_at', flat=True).first()
    if not last:
        return False, 0

    unlock_at = last + COOLDOWN
    if now >= unlock_at:
        return False, 0
    return True, int((unlock_at - now).total_seconds())


def record_reset_request(request, email):
    """
    Tiklash so'rovini yozadi.

    `successful=False` ATAYLAB: bu maydon shu yerda "muvaffaqiyat" emas,
    "sanaladigan urinish" ma'nosini beradi va hisoblagich mantig'i
    ikkala tur uchun bir xil qoladi. Email `username` ustuniga yoziladi.
    """
    return LoginAttempt.objects.create(
        username=(email or '')[:150],
        ip=client_ip(request),
        successful=False,
        purpose=LoginAttempt.Purpose.RESET,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:200],
    )


def reset_throttle_message(seconds) -> str:
    minutes = max(1, round(seconds / 60))
    return (
        f"Juda ko'p so'rov yuborildi. {minutes} daqiqadan keyin qayta "
        f"urinib ko'ring. Kod allaqachon kelgan bo'lsa, uni ishlatishingiz mumkin."
    )
