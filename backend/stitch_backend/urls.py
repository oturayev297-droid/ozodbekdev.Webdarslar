"""
URL configuration for stitch_backend project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.http import HttpResponse

urlpatterns = [
    # Railway healthcheck. SSL redirectdan ozod: settings.SECURE_REDIRECT_EXEMPT.
    path('health/', lambda r: HttpResponse('ok'), name='health'),
    # DJANGO ADMIN OLIB TASHLANDI.
    #
    # Uning barcha vazifalari `/panel/` ga ko'chirildi: bo'limlar,
    # darslar, test savollari, karta rekvizitlari, tarif narxi,
    # ota-ona bog'lanishlari.
    #
    # Nega butunlay olib tashlandi, o'chirilmay qoldirilmadi: ikkita
    # boshqaruv paneli bo'lsa, ikkalasida ham bir xil narsani
    # o'zgartirish mumkin bo'lardi va qaysi biri to'g'ri ekani
    # bilinmay qolardi. Ustiga `/admin/` — hujumchilar birinchi
    # navbatda urinib ko'radigan manzil.

    # Alohida deploy qilinadigan frontend uchun. Versiya manzilda:
    # frontend va backend bir vaqtda yangilanmaydi.
    path('api/v1/', include('api.urls')),
    path('panel/', include('panel.urls')),
    path('obuna/', include('billing.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    # DIQQAT: dars VIDEOLARI ataylab /media/ orqali berilmaydi. Ular
    # faqat /lessons/<id>/video/ endpointi orqali, huquq tekshirilib
    # uzatiladi. Bu yerda ochiq turadigan ikkita papka bor, xolos.
    #
    # NEGA DARS RASMLARI OCHIQ, VIDEO YOPIQ:
    # video — darsning O'ZI, uni himoyalash obunaning ma'nosi. Rasm esa
    # matnning kichik qismi: har bir rasmga alohida huquq so'rovi
    # qilish sahifani sekinlashtiradi, himoya qiymati esa deyarli nol —
    # rasmsiz matn baribir qulflangan bo'lib qoladi.
    for folder in ('profiles', 'lesson_images'):
        urlpatterns += static(
            settings.MEDIA_URL + folder + '/',
            document_root=settings.MEDIA_ROOT / folder,
        )

handler404 = 'core.views_errors.handler404'
handler500 = 'core.views_errors.handler500'
handler403 = 'core.views_errors.handler403'
