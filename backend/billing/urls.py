"""
`billing` manzillari — FAQAT TASHQI XIZMATLAR UCHUN.

O'quvchi ko'radigan sahifalar (tarif, to'lov so'rovi, tarix, Telegram
ulash) OLIB TASHLANDI: ular React frontendda va `/api/v1/subscription/`
orqali ishlaydi.

BU YERDAGI MANZILLARNI O'ZGARTIRIB BO'LMAYDI. Ular Payme, Click va
Telegram kabinetlariga AYNAN SHU ko'rinishda yozib qo'yilgan — manzil
o'zgarsa, to'lovlar jimgina kelmay qo'yadi va buni faqat pul
yo'qolganda sezasiz.
"""

from django.urls import path

from . import gateway_views, views

app_name = 'billing'

urlpatterns = [
    # To'lov sahifasiga yo'naltirish. Frontend bu manzilga havola
    # beradi, Django esa imzolangan to'lov havolasini quradi.
    path('pay/<int:request_id>/<str:provider>/', views.start_gateway_payment, name='start_payment'),

    # ── Payme / Click chaqiradigan manzillar ──
    path('payme/', gateway_views.payme_endpoint, name='payme_endpoint'),
    path('click/prepare/', gateway_views.click_prepare, name='click_prepare'),
    path('click/complete/', gateway_views.click_complete, name='click_complete'),

    # ── Telegram bot ──
    # Maxfiy qism `.env` dagi TELEGRAM_WEBHOOK_SECRET bilan mos kelishi
    # kerak. Busiz har kim bot nomidan soxta /start yuborib begona
    # hisobni o'ziga bog'lab olardi.
    path('telegram/hook/<str:secret>/', views.telegram_webhook, name='telegram_webhook'),
]
