"""
URL configuration for stitch_backend project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('obuna/', include('billing.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    # DIQQAT: dars videolari ATAYLAB /media/ orqali berilmaydi.
    # Ular faqat /lessons/<id>/video/ endpointi orqali, login talab qilib
    # uzatiladi. Bu yerda faqat profil rasmlari ochiq.
    urlpatterns += static(
        settings.MEDIA_URL + 'profiles/',
        document_root=settings.MEDIA_ROOT / 'profiles',
    )

handler404 = 'core.views_errors.handler404'
handler500 = 'core.views_errors.handler500'
handler403 = 'core.views_errors.handler403'
