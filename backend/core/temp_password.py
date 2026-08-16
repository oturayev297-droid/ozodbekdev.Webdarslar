"""
Admin tomonidan parolni tiklash.

MUAMMO. O'quvchi parolini unutadi, emaliga kira olmaydi (yoki email
umuman noto'g'ri kiritilgan) va adminga qo'ng'iroq qiladi. Admin
uning eski parolini KO'RA OLMAYDI va hech qachon ko'ra olmaydi:
Django parolni qaytarib bo'lmaydigan shaklda (PBKDF2 xesh) saqlaydi.
Ko'rsatish uchun parollarni ochiq matnda saqlash kerak bo'lardi —
u holda baza bir marta o'g'irlansa, hamma o'quvchining paroli
ketardi. Bunday tizimni sotib bo'lmaydi.

YECHIM. Admin bitta tugmani bosadi, tizim YANGI vaqtinchalik parol
yaratadi va uni adminga BIR MARTA ko'rsatadi. Admin o'quvchiga
aytadi, u kiradi. Natija foydalanuvchi uchun bir xil — hisobiga
qaytadi — lekin hech qayerda ochiq parol saqlanmaydi.

QO'SHIMCHA HIMOYA:

  * Parol xotirada emas, faqat javobda bir marta uzatiladi. Sahifa
    yangilansa yo'qoladi — logda ham, bazada ham qolmaydi.
  * Har tiklash `PasswordResetLog` ga yoziladi: kim, kimga, qachon.
    Kimdir o'quvchi hisobiga kirib olsa, iz qoladi.
  * Tiklash o'quvchining barcha ochiq seanslarini yopadi. Aks holda
    parolni bilgan begona odam eski seansda qolib ketardi.
  * Xodim hisobiga bu yo'l bilan tegib bo'lmaydi — panelga kirish
    huquqini bir admin ikkinchisidan tortib ololmasin.
"""

import logging
import secrets

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.utils import timezone

logger = logging.getLogger(__name__)

#: Chalkashtiradigan belgilar OLIB TASHLANGAN: 0/O, 1/l/I.
#: Parol telefonda OG'ZAKI aytiladi — "nol" bilan "katta o" ni
#: farqlash uchun qayta-qayta so'rashga to'g'ri kelardi.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"

#: Uch bo'lakdan iborat: aytishga va yozib olishga qulay.
GROUP_SIZE = 4
GROUPS = 3


class TempPasswordError(Exception):
    """Tiklash mumkin bo'lmagan holat."""


def generate() -> str:
    """
    Vaqtinchalik parol: `Kt7m-Zq9X-Rr2n`.

    `secrets` ishlatiladi, `random` emas: `random` oldindan
    aytib bo'ladigan ketma-ketlik beradi.
    """
    parts = [
        ''.join(secrets.choice(ALPHABET) for _ in range(GROUP_SIZE))
        for _ in range(GROUPS)
    ]
    return '-'.join(parts)


def reset(student: User, admin: User) -> str:
    """
    O'quvchiga yangi vaqtinchalik parol qo'yadi va uni QAYTARADI.

    Qaytarilgan qiymat hech qayerda saqlanmaydi — chaqiruvchi uni
    bir marta ko'rsatadi va unutadi.
    """
    if student.is_staff:
        raise TempPasswordError(
            "Xodim hisobining parolini bu yerdan tiklab bo'lmaydi. "
            "U `manage.py changepassword` orqali o'zgartiriladi."
        )
    if not student.is_active:
        raise TempPasswordError(
            "Hisob faolsizlantirilgan. Avval uni qayta faollashtiring."
        )

    password = generate()
    student.set_password(password)
    student.save(update_fields=['password'])

    _close_sessions(student)

    from .models import PasswordResetLog

    PasswordResetLog.objects.create(student=student, admin=admin)
    logger.info(
        "[PAROL] Admin %s -> %s hisobiga vaqtinchalik parol qo'ydi",
        admin.username, student.username,
    )

    # Admin o'z seansida qolsin: parol o'zgarishi sessiya xeshini
    # buzadi va admin o'zi chiqib ketardi.
    return password


def _close_sessions(student: User) -> int:
    """
    O'quvchining barcha ochiq seanslarini yopadi.

    NEGA: parolni bilib olgan begona odam allaqachon kirgan bo'lsa,
    parol almashgani uni chiqarib yubormasdi — seans alohida
    yashaydi. Tiklashning ma'nosi aynan shu odamni uzish.

    Django seanslarni kalit bo'yicha izlashga imkon bermaydi, shuning
    uchun faol seanslar ko'rib chiqiladi. Ular ko'p emas: eskilari
    `clearsessions` bilan tozalanadi.
    """
    closed = 0
    target = str(student.pk)
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        if session.get_decoded().get('_auth_user_id') == target:
            session.delete()
            closed += 1
    return closed
