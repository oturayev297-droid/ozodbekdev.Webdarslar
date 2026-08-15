"""
`core` manzillari.

ESKI O'QUVCHI SAHIFALARI OLIB TASHLANDI — ularning o'rnini React
frontend (`frontend/`) egalladi. Bu yerda faqat SHU IKKI SABABGA
KO'RA qoladigan manzillar bor:

1. FAYL UZATISH. Video va PDF sertifikat React'da qayta yozilmaydi:
   ular fayl, HTML emas. Ikkalasi ham huquq tekshiruvidan o'tadi va
   frontend ularga havola beradi.

2. TASHQI XIZMATLAR. `billing/urls.py` dagi Payme, Click va Telegram
   webhook manzillari — ularni o'sha xizmatlar kabinetiga yozib
   qo'yilgan, o'zgartirsak to'lovlar ishlamay qoladi.

Autentifikatsiya endi `/api/v1/auth/` da, panel esa `/panel/` da —
ikkalasining o'z kirishi bor.
"""

from django.urls import path

from . import views

urlpatterns = [
    # Video FAQAT shu manzil orqali beriladi va bu yerda obuna
    # tekshiriladi. Frontend faylni to'g'ridan-to'g'ri ololmaydi.
    path('lessons/<int:lesson_id>/video/', views.lesson_video, name='lesson_video'),

    # PDF serverda `reportlab` bilan chiziladi — brauzerda emas.
    path('certificates/<str:code>/pdf/', views.certificate_pdf, name='certificate_pdf'),
]
