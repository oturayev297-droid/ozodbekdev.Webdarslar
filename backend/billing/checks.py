"""
Sozlama tekshiruvlari (`manage.py check`).

NEGA KERAK. `.env` dagi kalit nomi xato terilsa, `django-environ`
jimgina standart qiymatni oladi va hech kim buni sezmaydi. Aynan
shunday bo'ldi: `.env` da `TELEGRAM_ADMIN_CHAT_ID` (birlikda)
yozilgan edi, kod esa `TELEGRAM_ADMIN_CHAT_IDS` (ko'plikda)
o'qiydi. Natijada bot ishlab turdi, o'quvchilarga xabar bordi,
lekin ADMINGA hech narsa kelmadi — va buni faqat "nega menga
xabar kelmayapti" degan savoldan keyin bilish mumkin edi.

Bu yerdagi tekshiruvlar shunday jim nosozliklarni ko'rinadigan
qiladi. Ular OGOHLANTIRISH (`Warning`), xato emas: sozlanmagan
Telegram saytni ishlashdan to'xtatmasligi kerak.
"""

from django.conf import settings
from django.core.checks import Warning, register


@register()
def telegram_settings(app_configs, **kwargs):
    """Telegram sozlamalarining o'zaro mosligi."""
    issues = []

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    username = getattr(settings, 'TELEGRAM_BOT_USERNAME', '')
    admins = getattr(settings, 'TELEGRAM_ADMIN_CHAT_IDS', [])
    secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')

    if not token:
        # Butunlay sozlanmagan — bu ongli tanlov bo'lishi mumkin.
        return issues

    if not admins:
        issues.append(Warning(
            "Telegram boti sozlangan, lekin TELEGRAM_ADMIN_CHAT_IDS bo'sh.",
            hint=(
                "Yangi ro'yxatdan o'tish, to'lov so'rovi va chek haqidagi "
                "xabarlar HECH KIMGA bormaydi. .env ga chat ID ni yozing "
                "(@userinfobot dan olinadi). Kalit nomi KO'PLIKDA: "
                "TELEGRAM_ADMIN_CHAT_IDS"
            ),
            id='billing.W001',
        ))

    if not username:
        issues.append(Warning(
            "TELEGRAM_BOT_USERNAME bo'sh.",
            hint=(
                "Hisobni ulash havolasi shundan quriladi "
                "(t.me/<username>?start=...). Bo'sh bo'lsa havola "
                "ishlamaydi va o'quvchi Telegramini ulay olmaydi."
            ),
            id='billing.W002',
        ))

    if not secret:
        issues.append(Warning(
            "TELEGRAM_WEBHOOK_SECRET bo'sh.",
            hint=(
                "Webhook manzili shu qiymat bilan himoyalanadi. Bo'sh "
                "bo'lsa webhook 404 qaytaradi — ya'ni productionda bot "
                "kiruvchi xabarlarni umuman qabul qilmaydi."
            ),
            id='billing.W003',
        ))

    return issues


@register()
def payment_settings(app_configs, **kwargs):
    """To'lov tizimlari yarim sozlanib qolmasin."""
    issues = []

    payme_id = getattr(settings, 'PAYME_MERCHANT_ID', '')
    payme_key = getattr(settings, 'PAYME_KEY', '')
    if bool(payme_id) != bool(payme_key):
        issues.append(Warning(
            "Payme yarim sozlangan.",
            hint=(
                "PAYME_MERCHANT_ID va PAYME_KEY ikkalasi ham kerak. "
                "Bittasi bo'sh bo'lsa tugma ko'rinadi, lekin to'lov "
                "o'tmaydi."
            ),
            id='billing.W004',
        ))

    click_service = getattr(settings, 'CLICK_SERVICE_ID', '')
    click_merchant = getattr(settings, 'CLICK_MERCHANT_ID', '')
    click_secret = getattr(settings, 'CLICK_SECRET_KEY', '')
    filled = [bool(click_service), bool(click_merchant), bool(click_secret)]
    if any(filled) and not all(filled):
        issues.append(Warning(
            "Click yarim sozlangan.",
            hint=(
                "CLICK_SERVICE_ID, CLICK_MERCHANT_ID va CLICK_SECRET_KEY "
                "uchalasi ham kerak."
            ),
            id='billing.W005',
        ))

    return issues
