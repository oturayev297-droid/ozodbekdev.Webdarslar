"""
Pullik dars videosi uchun qisqa muddatli token
==============================================

NEGA SESSION EMAS:

Frontend (Vercel) va backend (Railway) turli domenlarda. `<video>`
tegi Django session cookie'sini cross-site yubormaydi, frontend esa
JWT ishlatadi — `<video src>` ga sarlavha qo'shib bo'lmaydi. Natijada
tizimga kirgan odam ham `/lessons/<id>/video/` da login sahifasiga
yo'naltirilardi va pleyerga HTML qaytardi.

QANDAY ISHLAYDI:

API darsni qaytarayotganda huquqni tekshiradi va `video_url` ga
`?t=<token>` qo'shadi. Video endpointi `request.user` ga emas, shu
tokenga qaraydi. Token:

  * bitta DARSGA bog'langan — 27-dars tokeni 28-darsni ochmaydi;
  * `TOKEN_TTL` dan keyin o'ladi — tarqatilgan havola uzoq yashamaydi;
  * `SECRET_KEY` bilan imzolangan — qo'lda yasab bo'lmaydi.

Ichidagi `user_id` huquq uchun emas: u tokenni har foydalanuvchi uchun
alohida qiladi va tarqalgan havolaning kimdan chiqqanini aniqlashga
imkon beradi.
"""

from django.core import signing

#: Token necha soniya amal qiladi.
TOKEN_TTL = 15 * 60

_SALT = 'core.lesson-video'


def make(lesson_id: int, user_id: int) -> str:
    """`lesson_id` darsining videosi uchun token."""
    return signing.TimestampSigner(salt=_SALT).sign(f"{lesson_id}:{user_id}")


def check(token: str, lesson_id: int):
    """
    Tokenni tekshiradi.

    Qaytaradi: to'g'ri bo'lsa `user_id`, aks holda None — token yo'q,
    soxta, muddati o'tgan yoki boshqa darsniki bo'lsa ham.
    """
    if not token:
        return None
    try:
        # SignatureExpired ham BadSignature'ning bolasi
        value = signing.TimestampSigner(salt=_SALT).unsign(token, max_age=TOKEN_TTL)
    except signing.BadSignature:
        return None

    token_lesson, _, user_id = value.partition(':')
    if token_lesson != str(lesson_id) or not user_id.isdigit():
        return None
    return int(user_id)
