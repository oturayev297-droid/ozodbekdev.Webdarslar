"""
Parolni tiklash
===============

Kodlar bazada (`core_passwordreset`), XESHLANGAN holda saqlanadi.
Ochiq kod hech qayerda turmaydi va javob tanasiga HECH QACHON qo'shilmaydi.

ANTI-ENUMERATSIYA: javob email bazada bor-yo'qligidan QAT'I NAZAR bir xil
bo'ladi. Aks holda javobning o'zi "bu email ro'yxatdan o'tganmi" degan
savolga javob beruvchi vositaga aylanardi.
"""

import hashlib
import logging
import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import PasswordReset

logger = logging.getLogger(__name__)

#: Kod amal qilish muddati (daqiqa)
CODE_TTL_MINUTES = 15

#: Bitta kodga nechta noto'g'ri urinish beriladi
MAX_ATTEMPTS = 5

#: Email bor-yo'qligidan qat'i nazar beriladigan javob
GENERIC_MESSAGE = (
    f"Agar bu email ro'yxatdan o'tgan bo'lsa, tiklash kodi yuborildi. "
    f"Kod {CODE_TTL_MINUTES} daqiqa amal qiladi."
)

#: Sabab oshkor qilinmaydi: "email topilmadi", "kod xato" va "muddati
#: o'tgan" uchun bitta xabar.
INVALID_MESSAGE = "Tiklash kodi noto'g'ri yoki muddati o'tgan."


class ResetError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def hash_code(code: str) -> str:
    """Kodni bir tomonlama xeshlash — bazada ochiq kod turmaydi."""
    return hashlib.sha256(code.encode()).hexdigest()


def generate_code() -> str:
    """
    6 xonali kod.

    `random` EMAS — u kriptografik emas, tiklash kodi esa aynan hisobga
    kirish vositasi, ya'ni taxmin qilinmasligi kerak.
    """
    return f"{secrets.randbelow(1_000_000):06d}"


def _find_user(email: str):
    email = (email or "").strip().lower()
    if not email:
        return None
    return User.objects.filter(email__iexact=email, is_active=True).first()


@transaction.atomic
def request_reset(email: str) -> str:
    """
    Tiklash kodini yaratadi va emailga yuboradi.

    Javob har doim bir xil — mavjud bo'lmagan email ham xuddi shunday
    javob oladi.
    """
    user = _find_user(email)
    if not user:
        logger.info("[AUTH] Parol tiklash: email topilmadi (%s)", email)
        return GENERIC_MESSAGE

    code = generate_code()

    # Avvalgi ishlatilmagan kodlar bekor qilinadi: bir vaqtda faqat
    # bitta amaldagi kod bo'lsin, aks holda eski kodlar ham ochiq
    # qolaverardi.
    PasswordReset.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )

    PasswordReset.objects.create(
        user=user,
        code_hash=hash_code(code),
        expires_at=timezone.now() + timedelta(minutes=CODE_TTL_MINUTES),
    )

    _send_code_email(user, code)
    return GENERIC_MESSAGE


def _send_code_email(user, code: str):
    """
    Kodni yuboradi.

    XATO TASHLAMAYDI: SMTP ishlamasa ham chaqiruvchi oqim davom etadi —
    "xat ketdimi yo'qmi" degan farq foydalanuvchiga oshkor qilinmasligi
    kerak (enumeratsiyaga qarshi).

    SMTP sozlanmagan bo'lsa Django console backend ishlatiladi va kod
    terminalga chiqadi — lokal ishlab chiqish uchun.
    """
    subject = "Nexus — parolni tiklash kodi"
    body = (
        f"Assalomu alaykum, {user.profile.full_name or user.username}!\n\n"
        f"Parolni tiklash kodingiz: {code}\n\n"
        f"Kod {CODE_TTL_MINUTES} daqiqa amal qiladi va faqat bir marta ishlaydi.\n\n"
        f"Agar bu so'rovni siz yubormagan bo'lsangiz, bu xatni e'tiborsiz "
        f"qoldiring — parolingiz o'zgarmaydi.\n"
    )
    try:
        send_mail(subject, body, None, [user.email], fail_silently=False)
        logger.info("[AUTH] Tiklash kodi yuborildi: userId=%s", user.pk)
    except Exception as exc:
        logger.error("[AUTH] Tiklash kodini yuborib bo'lmadi (userId=%s): %s", user.pk, exc)


def confirm_reset(email: str, code: str, new_password: str) -> str:
    """
    Kod va yangi parol bilan parolni yangilaydi.

    DIQQAT — butun funksiya `@transaction.atomic` BO'LMASLIGI kerak.
    Aks holda `ResetError` ko'tarilganda `attempts += 1` ham orqaga
    qaytariladi va urinishlar hisoblagichi hech qachon o'smaydi, ya'ni
    6 xonali kodni cheksiz taxmin qilib bo'ladi. Shuning uchun:
      * tekshiruv natijasi (hisoblagich) alohida tranzaksiyada SAQLANADI,
      * xato esa tranzaksiya YOPILGANDAN KEYIN ko'tariladi.
    """

    # Parol talabini kod tekshiruvidan OLDIN bajaramiz: bo'sh urinish
    # hisobga olinib, amaldagi kod bekorga sarflanmasin.
    try:
        validate_password(new_password)
    except ValidationError as exc:
        raise ResetError(" ".join(exc.messages))

    user = _find_user(email)
    if not user:
        raise ResetError(INVALID_MESSAGE)

    error = None
    record = None

    # ── 1-qadam: kodni tekshirish. Bu blok HAR DOIM commit bo'ladi. ──
    with transaction.atomic():
        record = (
            PasswordReset.objects.select_for_update()
            .filter(user=user, used_at__isnull=True, expires_at__gt=timezone.now())
            .order_by('-created_at')
            .first()
        )

        if record is None:
            error = INVALID_MESSAGE

        elif record.attempts >= MAX_ATTEMPTS:
            # Kod kuydiriladi — cheksiz taxmin qilib bo'lmasin
            record.used_at = timezone.now()
            record.save(update_fields=['used_at'])
            error = "Juda ko'p noto'g'ri urinish. Yangi kod so'rang."

        # Doimiy vaqtli solishtirish — vaqt bo'yicha sizib chiqishga qarshi
        elif not secrets.compare_digest(record.code_hash, hash_code((code or "").strip())):
            record.attempts += 1
            record.save(update_fields=['attempts'])
            error = INVALID_MESSAGE

    if error:
        raise ResetError(error)

    # ── 2-qadam: parol yangilanishi va kodning kuyishi BIRGA bo'lishi
    # kerak — aks holda parol o'zgarib, kod amalda qolib ketishi mumkin.
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=['password'])

        record.used_at = timezone.now()
        record.save(update_fields=['used_at'])

    logger.info("[AUTH] Parol tiklandi: userId=%s", user.pk)
    return "Parolingiz muvaffaqiyatli yangilandi. Endi yangi parol bilan kiring."
