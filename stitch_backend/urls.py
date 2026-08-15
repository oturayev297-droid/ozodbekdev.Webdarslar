"""
URL configuration for stitch_backend project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django'ning standart paneli ZAXIRA yo'l sifatida qoladi: kundalik
    # ish `/panel/` da, nozik holatlar (model darajasidagi tuzatish)
    # esa shu yerda bajariladi.
    path('admin/', admin.site.urls),
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
