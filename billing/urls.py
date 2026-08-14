from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.plans, name='plans'),
    path('request/', views.create_request, name='create_request'),
    path('request/receipt/', views.mark_receipt_sent, name='mark_receipt_sent'),
    path('request/cancel/', views.cancel_request, name='cancel_request'),
    path('history/', views.my_history, name='history'),

    # Telegram
    path('telegram/link/', views.telegram_link, name='telegram_link'),
    path('telegram/unlink/', views.telegram_unlink, name='telegram_unlink'),
    # Maxfiy manzil — `.env` dagi TELEGRAM_WEBHOOK_SECRET bilan mos kelishi kerak
    path('telegram/hook/<str:secret>/', views.telegram_webhook, name='telegram_webhook'),
]
