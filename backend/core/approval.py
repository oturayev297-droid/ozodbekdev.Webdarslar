"""
Admin ruxsati darvozasi
=======================

Ro'yxatdan o'tishning O'ZI kirish huquqini bermaydi. Admin paneldan
ruxsat bermaguncha o'quvchi kontentni ko'rmaydi.

BU OBUNANING O'RNINI BOSMAYDI — ikkita alohida darvoza:

    ruxsat  = adminning bu odamni tanishi. BIR MARTA beriladi.
    obuna   = joriy oy uchun to'lov. HAR OY yangilanadi.

Ikkalasi ham o'tishi kerak. Chalkashtirilsa: ruxsat obunani almashtirsa,
bir marta to'lagan odam abadiy kirardi; obuna ruxsatni almashtirsa,
admin kimni qabul qilishini nazorat qila olmasdi.

NEGA KIRISH BLOKLANMAYDI, faqat kontent:

O'quvchi tizimga KIRA OLADI va o'z holatini ko'radi ("ruxsat
kutilmoqda"). Login butunlay bloklansa, u to'g'ri parol bilan ham
kira olmay, "parolim ishlamayapti" deb o'ylardi va admin bilan
bog'lanish o'rniga qayta-qayta urinardi. Bu panel logini uchun
qabul qilingan qaror bilan bir xil.
"""

from functools import wraps

from django.shortcuts import redirect
from django.utils import timezone


def is_approved(user) -> bool:
    """
    Foydalanuvchiga ruxsat berilganmi.

    XODIM HAR DOIM O'TADI: admin o'ziga ruxsat berib o'tirmasin. Bu
    `billing.services.get_state` dagi qoida bilan bir xil naqsh.
    """
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True

    profile = getattr(user, 'profile', None)
    # Profil yo'q bo'lsa — ruxsat ham yo'q (fail closed). Amalda
    # `post_save` signali har foydalanuvchiga profil ochib beradi.
    return bool(profile and profile.is_approved)


def approval_required(view):
    """
    Kontent sahifalarini himoyalaydi.

    Ruxsatsiz foydalanuvchi kutish sahifasiga yuboriladi. `login_required`
    QO'SHIMCHA emas — u alohida qo'yiladi, chunki bu ikki xil holat:
    kirmagan odam login sahifasiga, kirgan-u ruxsatsizi kutish
    sahifasiga ketishi kerak.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and not is_approved(request.user):
            return redirect('pending_approval')
        return view(request, *args, **kwargs)

    return wrapper


def approve(profile, admin=None):
    """
    Ruxsat beradi.

    Rad etish sababi TOZALANADI: odam qayta ko'rib chiqilib qabul
    qilingan bo'lsa, eski rad javobi profilida qolib ketmasligi kerak.
    """
    profile.is_approved = True
    profile.approved_at = timezone.now()
    profile.approved_by = admin
    profile.rejection_reason = ''
    profile.save(update_fields=['is_approved', 'approved_at', 'approved_by', 'rejection_reason'])
    return profile


def revoke(profile, reason='', admin=None):
    """
    Ruxsatni olib tashlaydi.

    `approved_at` ATAYLAB tozalanmaydi: qachon qabul qilingani tarix
    sifatida qolsin — keyin "bu odam qachondan beri bizda edi" degan
    savolga javob kerak bo'ladi.
    """
    profile.is_approved = False
    profile.rejection_reason = (reason or '').strip()
    profile.approved_by = admin
    profile.save(update_fields=['is_approved', 'rejection_reason', 'approved_by'])
    return profile
