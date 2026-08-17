"""
Sozlama tekshiruvlari.

NEGA KERAK. `.env` dagi kalit nomi xato terilsa, `django-environ`
jimgina standart qiymatni oladi va HECH QANDAY XATO CHIQMAYDI.
Aynan shunday bo'ldi: `.env` da `TELEGRAM_ADMIN_CHAT_ID` (birlikda)
yozilgan edi, kod esa ko'plikda o'qiydi. Bot ishlab turdi,
o'quvchilarga xabar bordi, lekin adminga hech narsa kelmadi —
buni faqat "nega menga xabar kelmayapti" degan savoldan keyin
bilish mumkin edi.
"""

from django.test import SimpleTestCase, override_settings

from billing import checks


def ids(issues):
    return {issue.id for issue in issues}


class TelegramCheckTests(SimpleTestCase):
    @override_settings(TELEGRAM_BOT_TOKEN='')
    def test_sozlanmagan_bot_ogohlantirmaydi(self):
        """
        Telegram umuman ishlatilmasa — bu ongli tanlov, shovqin
        qilmaslik kerak.
        """
        self.assertEqual(checks.telegram_settings(None), [])

    @override_settings(
        TELEGRAM_BOT_TOKEN='token',
        TELEGRAM_BOT_USERNAME='bot',
        TELEGRAM_WEBHOOK_SECRET='kalit',
        TELEGRAM_ADMIN_CHAT_IDS=[],
    )
    def test_ADMIN_CHAT_ID_BOSH_bolsa_ogohlantiradi(self):
        """Eng muhim tekshiruv — aynan shu nuqson jimgina o'tib ketgan edi."""
        issues = checks.telegram_settings(None)

        self.assertIn('billing.W001', ids(issues))
        hint = next(i for i in issues if i.id == 'billing.W001').hint
        self.assertIn('TELEGRAM_ADMIN_CHAT_IDS', hint, 'To\'g\'ri kalit nomi aytilmagan')

    @override_settings(
        TELEGRAM_BOT_TOKEN='token',
        TELEGRAM_BOT_USERNAME='',
        TELEGRAM_WEBHOOK_SECRET='kalit',
        TELEGRAM_ADMIN_CHAT_IDS=['1'],
    )
    def test_username_bosh_bolsa_ogohlantiradi(self):
        self.assertIn('billing.W002', ids(checks.telegram_settings(None)))

    @override_settings(
        TELEGRAM_BOT_TOKEN='token',
        TELEGRAM_BOT_USERNAME='bot',
        TELEGRAM_WEBHOOK_SECRET='',
        TELEGRAM_ADMIN_CHAT_IDS=['1'],
    )
    def test_webhook_kaliti_bosh_bolsa_ogohlantiradi(self):
        self.assertIn('billing.W003', ids(checks.telegram_settings(None)))

    @override_settings(
        TELEGRAM_BOT_TOKEN='token',
        TELEGRAM_BOT_USERNAME='bot',
        TELEGRAM_WEBHOOK_SECRET='kalit',
        # Soxta qiymat. HAQIQIY chat ID yozilmaydi: u shaxsiy
        # identifikator va repozitoriy ochiq.
        TELEGRAM_ADMIN_CHAT_IDS=['100200300'],
    )
    def test_togri_sozlanganda_jim(self):
        self.assertEqual(checks.telegram_settings(None), [])


class PaymentCheckTests(SimpleTestCase):
    """To'lov tizimi yarim sozlanib qolsa, tugma ko'rinadi-yu ishlamaydi."""

    @override_settings(PAYME_MERCHANT_ID='abc', PAYME_KEY='')
    def test_payme_yarim_sozlangan(self):
        self.assertIn('billing.W004', ids(checks.payment_settings(None)))

    @override_settings(PAYME_MERCHANT_ID='abc', PAYME_KEY='kalit')
    def test_payme_toliq_sozlangan(self):
        self.assertNotIn('billing.W004', ids(checks.payment_settings(None)))

    @override_settings(
        CLICK_SERVICE_ID='1', CLICK_MERCHANT_ID='2', CLICK_SECRET_KEY='',
    )
    def test_click_yarim_sozlangan(self):
        self.assertIn('billing.W005', ids(checks.payment_settings(None)))

    @override_settings(
        PAYME_MERCHANT_ID='', PAYME_KEY='',
        CLICK_SERVICE_ID='', CLICK_MERCHANT_ID='', CLICK_SECRET_KEY='',
    )
    def test_umuman_sozlanmagan_bolsa_jim(self):
        """Qo'lda tasdiqlash bilan ishlash — to'liq haqiqiy holat."""
        self.assertEqual(checks.payment_settings(None), [])
