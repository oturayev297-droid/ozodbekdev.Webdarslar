"""
Muharrir topshiriqlarini tekshirish
===================================

KOD SERVERDA ISHLAMAYDI. U brauzerda, o'quvchining o'z mashinasida
bajariladi (`frontend/src/lib/runner.ts`) — begona kodni serverda
ijro etish serverni begona odamga topshirish demak. Server bu yerda
faqat NATIJANI solishtiradi.

KUTILGAN NATIJA MIJOZGA YUBORILMAYDI. Aks holda u sahifa
yuklanishidayoq javobga tushib qolar va topshiriqning ma'nosi
qolmasdi — xuddi test javoblari kabi (`api/serializers.py` ga
qarang). Shu sabab tekshiruv shu yerda, serverda.

BU IMTIHON EMAS. Natija brauzerdan keladi, ya'ni uni qo'lda ham
yuborish mumkin. Bu ataylab qabul qilingan: muharrir — o'rganish
quroli, sertifikat esa testlardan beriladi va u yerda javoblar
mijozga umuman ko'rinmaydi.
"""

import re


def normalize(text: str) -> str:
    """
    Solishtirishdan oldin matnni tozalaydi.

    NEGA KERAK: `print()` oxirida qator tashlaydi, brauzer `\r\n`
    yuborishi mumkin, o'quvchi esa qator oxiriga bo'sh joy qo'yib
    yuboradi. Bularning birortasi ham XATO EMAS — natija ekranda
    bir xil ko'rinadi. Tozalanmasa, to'g'ri yechim "noto'g'ri" deb
    rad etilar va o'quvchi nimasi xato ekanini hech qachon
    topolmasdi.

    NIMA SAQLANADI: harflar registri va qatorlar TARTIBI. Ular
    natijaning o'zi — ularga ko'z yumish tekshiruvni ma'nosiz
    qilardi.
    """
    text = (text or '').replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.rstrip() for line in text.split('\n')]

    # Oxiridagi bo'sh qatorlar tashlanadi: `print()` dan keyin
    # qoladigan qator har doim bor va u natijaning qismi emas.
    while lines and not lines[-1]:
        lines.pop()

    return '\n'.join(lines)


def compare(expected: str, actual: str) -> bool:
    return normalize(expected) == normalize(actual)


def first_difference(expected: str, actual: str):
    """
    Birinchi farq qilgan qator raqami va ikkala tomondagi matn.

    "Noto'g'ri" degan javobning o'zi hech narsa o'rgatmaydi. Qaysi
    qatorda, nima kutilgani va nima chiqqani ko'rsatilsa, o'quvchi
    xatoni O'ZI topadi — yechimni ochib ko'rishga hojat qolmaydi.

    Qaytaradi: `(qator_raqami, kutilgan, chiqqan)` yoki farq
    bo'lmasa `None`.
    """
    exp_lines = normalize(expected).split('\n')
    act_lines = normalize(actual).split('\n')

    for index in range(max(len(exp_lines), len(act_lines))):
        exp = exp_lines[index] if index < len(exp_lines) else None
        act = act_lines[index] if index < len(act_lines) else None
        if exp != act:
            return index + 1, exp, act

    return None


#: Xato matnida uchraydigan naqshlar. Til farq qiladi, lekin
#: ikkalasida ham xato SATRDA keladi — muharrir uni alohida
#: ajratib ko'rsatishi uchun shu yetadi.
_ERROR_HINT = re.compile(r'(Error|Exception|Traceback)', re.IGNORECASE)


def looks_like_error(text: str) -> bool:
    return bool(_ERROR_HINT.search(text or ''))
