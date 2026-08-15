"""
Testlar uchun umumiy yordamchilar.

Bu MODUL O'ZI TEST EMAS — nomi `test_` bilan boshlanmagani ataylab,
aks holda Django uni test moduli deb topib, ichida test yo'qligidan
shikoyat qilardi.
"""

from core.models import Profile


def approve_all():
    """
    Barcha profillarga admin ruxsatini beradi.

    NEGA KERAK: `Profile.is_approved` standart holatda `False` —
    ro'yxatdan o'tgan odam admin tasdiqlamaguncha kontentni ko'rmaydi.
    Bu to'g'ri xatti-harakat va u `core.tests_approval` da alohida
    sinaladi.

    Lekin QOLGAN testlarning mavzusi boshqa: obuna, to'lov, sertifikat,
    AI mentor. Ular uchun ruxsat shunchaki fon shartidir. Har birida
    uni qo'lda ochib o'tirish o'rniga, `setUp` oxirida shu funksiya
    chaqiriladi.

    XAVFSIZ: har bir test o'z tranzaksiyasida ishlaydi va tugagach
    orqaga qaytariladi, shuning uchun bu chaqiruv boshqa testlarga
    ta'sir qilmaydi.
    """
    Profile.objects.update(is_approved=True)
