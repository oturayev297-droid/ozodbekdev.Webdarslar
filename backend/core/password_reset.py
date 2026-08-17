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


def _find_users(email: str):
    """
    Shu emaildagi BARCHA faol hisoblar.

    RO'YXAT QAYTARADI, bitta foydalanuvchi emas. Django'da email
    yagona bo'lishi shart emas va bu platformada bu ataylab shunday:
    oilada ota-ona va farzand bitta pochtadan foydalanishi tabiiy.

    Ilgari bu yerda `.first()` bor edi va oqibati jiddiy edi: bitta
    emailga bog'langan bir nechta hisobdan FAQAT BIRINCHISI parolini
    tiklay olardi. Qolganlari kod so'rasa, kod boshqa odamning
    hisobiga yaratilardi — ular parolini hech qachon tiklay olmasdi.
    """
    email = (email or "").strip().lower()
    if not email:
        return []
    return list(User.objects.filter(email__iexact=email, is_active=True).order_by('id'))


@transaction.atomic
def request_reset(email: str) -> str:
    """
    Tiklash kodini yaratadi va emailga yuboradi.

    Javob har doim bir xil — mavjud bo'lmagan email ham xuddi shunday
    javob oladi.
    """
    users = _find_users(email)
    if not users:
        logger.info("[AUTH] Parol tiklash: email topilmadi (%s)", email)
        return GENERIC_MESSAGE

    # HAR BIR HISOBGA O'Z KODI. Bitta emailda bir nechta hisob bo'lsa,
    # odam qaysi login uchun qaysi kod ekanini xatdan ko'radi va
    # kerakli hisobini tiklaydi.
    pairs = []
    for user in users:
        # Avvalgi ishlatilmagan kodlar bekor qilinadi: bir vaqtda
        # faqat bitta amaldagi kod bo'lsin, aks holda eski kodlar ham
        # ochiq qolaverardi.
        PasswordReset.objects.filter(user=user, used_at__isnull=True).update(
            used_at=timezone.now()
        )

        code = generate_code()
        PasswordReset.objects.create(
            user=user,
            code_hash=hash_code(code),
            expires_at=timezone.now() + timedelta(minutes=CODE_TTL_MINUTES),
        )
        pairs.append((user, code))

    _send_code_email(email, pairs)
    return GENERIC_MESSAGE


def _send_code_email(email: str, pairs):
    """
    Kodlarni BITTA xat bilan yuboradi.

    `pairs` — `(user, code)` juftliklari. Bitta emailga bir nechta
    hisob bog'langan bo'lsa, xatda har bir login o'z kodi bilan
    ko'rsatiladi — aks holda odam qaysi kod qaysi hisobga tegishli
    ekanini bilmasdi.

    XATO TASHLAMAYDI: SMTP ishlamasa ham chaqiruvchi oqim davom etadi —
    "xat ketdimi yo'qmi" degan farq foydalanuvchiga oshkor qilinmasligi
    kerak (enumeratsiyaga qarshi).

    SMTP sozlanmagan bo'lsa Django console backend ishlatiladi va kod
    terminalga chiqadi — lokal ishlab chiqish uchun.
    """
    subject = "Nexus — parolni tiklash kodi"

    if len(pairs) == 1:
        user, code = pairs[0]
        greeting = user.profile.full_name or user.username
        body = (
            f"Assalomu alaykum, {greeting}!\n\n"
            f"Parolni tiklash kodingiz: {code}\n\n"
        )
    else:
        lines = [f"  {user.username} — kod: {code}" for user, code in pairs]
        body = (
            "Assalomu alaykum!\n\n"
            f"Bu pochtaga {len(pairs)} ta hisob bog'langan. Har biriga "
            f"alohida kod:\n\n"
            + "\n".join(lines)
            + "\n\nQaysi hisobni tiklamoqchi bo'lsangiz, o'sha kodni kiriting.\n\n"
        )

    body += (
        f"Kod {CODE_TTL_MINUTES} daqiqa amal qiladi va faqat bir marta ishlaydi.\n\n"
        f"Agar bu so'rovni siz yubormagan bo'lsangiz, bu xatni e'tiborsiz "
        f"qoldiring — parolingiz o'zgarmaydi.\n"
    )

    try:
        send_mail(subject, body, None, [email], fail_silently=False)
        logger.info(
            "[AUTH] Tiklash kodi yuborildi: %d ta hisob uchun", len(pairs)
        )
    except Exception as exc:
        logger.error("[AUTH] Tiklash kodini yuborib bo'lmadi: %s", exc)


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

    users = _find_users(email)
    if not users:
        raise ResetError(INVALID_MESSAGE)

    error = None
    record = None

    # ── 1-qadam: kodni tekshirish. Bu blok HAR DOIM commit bo'ladi. ──
    with transaction.atomic():
        # HISOBNI KOD ANIQLAYDI, email emas.
        #
        # Ilgari bu yerda emaildan topilgan BIRINCHI foydalanuvchi
        # olinardi. Bitta emailga bir nechta hisob bog'langan bo'lsa,
        # ikkinchi odam to'g'ri kod kiritsa ham birinchi odamning
        # paroli almashardi — yoki umuman hech nima ishlamasdi.
        candidates = list(
            PasswordReset.objects.select_for_update()
            .filter(
                user__in=users,
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .order_by('-created_at')
        )

        given = hash_code((code or "").strip())
        # Doimiy vaqtli solishtirish — vaqt bo'yicha sizib chiqishga qarshi
        record = next(
            (r for r in candidates if secrets.compare_digest(r.code_hash, given)),
            None,
        )

        if not candidates:
            error = INVALID_MESSAGE

        elif record is None:
            # Kod hech qaysi hisobga to'g'ri kelmadi. Urinish HAMMA
            # nomzodga yoziladi: aks holda hujumchi bir hisobning
            # cheklovini boshqasi orqali aylanib o'tardi.
            for candidate in candidates:
                candidate.attempts += 1
                candidate.save(update_fields=['attempts'])
            error = INVALID_MESSAGE

        elif record.attempts >= MAX_ATTEMPTS:
            # Kod kuydiriladi — cheksiz taxmin qilib bo'lmasin
            record.used_at = timezone.now()
            record.save(update_fields=['used_at'])
            error = "Juda ko'p noto'g'ri urinish. Yangi kod so'rang."
            record = None

    if record is not None:
        user = record.user

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
