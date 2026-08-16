"""
Telegram bot: kiruvchi xabarlarni qayta ishlash.

E'TIBOR QARATILGAN JOYLAR:

  * BIRINCHI MARTA OCHGAN ODAM tushunarli javob olishi — u hech
    qanday havola ochmagan bo'lsa ham "havola eskirgan" deyilmasligi
  * Havola BIR MARTA ishlashi — ikkinchi odam o'sha havola bilan
    begona hisobni o'ziga bog'lab olmasligi
  * Webhook va `telegram_poll` BIR XIL ishlashi — lokalda ishlagan
    narsa serverda ham ishlashi
"""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from billing import telegram


def make_user(username='oquvchi'):
    user = User.objects.create_user(username, password='juda-maxfiy-parol-3')
    profile = user.profile
    profile.full_name = 'Diyorbek Sobirov'
    profile.telegram_chat_id = ''
    profile.save(update_fields=['full_name', 'telegram_chat_id'])
    return user


def update_for(text, chat_id=777001):
    return {
        'update_id': 1,
        'message': {
            'message_id': 1,
            'date': 0,
            'chat': {'id': chat_id, 'type': 'private', 'first_name': 'Test'},
            'from': {'id': chat_id, 'is_bot': False, 'first_name': 'Test'},
            'text': text,
        },
    }


@override_settings(
    TELEGRAM_BOT_TOKEN='sinov-token',
    TELEGRAM_BOT_USERNAME='sinov_bot',
    TELEGRAM_WEBHOOK_SECRET='sinov-maxfiy-kalit',
    TELEGRAM_ADMIN_CHAT_IDS=[],
)
class HandleUpdateTests(TestCase):
    """`telegram.handle_update` — webhook ham, poll ham shuni chaqiradi."""

    def setUp(self):
        self.student = make_user()

    def _run(self, text, chat_id=777001):
        sent = []
        with patch(
            'billing.telegram._post',
            side_effect=lambda method, payload: sent.append(payload) or True,
        ):
            handled = telegram.handle_update(update_for(text, chat_id))
        return handled, sent

    def test_BIRINCHI_MARTA_ochganga_tushunarli_javob(self):
        """
        Odam botni ochib «Start» bosadi — hech qanday havola yo'q.
        Ilgari unga "Havola eskirgan" deyilardi va u nima
        qilishini bilmasdi.
        """
        handled, sent = self._run('/start')

        self.assertTrue(handled)
        text = sent[0]['text']
        self.assertNotIn('eskirgan', text)
        self.assertIn('Profil', text, 'Nima qilish kerakligi aytilmagan')

    def test_togri_havola_hisobni_ulaydi(self):
        link = telegram.create_link_token(self.student)
        token = link.rsplit('=', 1)[-1]

        handled, sent = self._run(f'/start {token}')

        self.assertTrue(handled)
        self.student.refresh_from_db()
        self.assertEqual(self.student.profile.telegram_chat_id, '777001')
        self.assertIn('ulandi', sent[0]['text'])

    def test_havola_IKKINCHI_MARTA_ishlamaydi(self):
        """
        Eng muhim tekshiruv: havola boshqa odamga yetib borsa, u
        begona hisobni o'ziga bog'lab, o'sha odamning to'lov
        rekvizitlari va xabarlarini olardi.
        """
        link = telegram.create_link_token(self.student)
        token = link.rsplit('=', 1)[-1]
        self._run(f'/start {token}', chat_id=777001)

        _handled, sent = self._run(f'/start {token}', chat_id=999002)

        self.assertIn('eskirgan', sent[0]['text'])
        self.student.refresh_from_db()
        self.assertEqual(
            self.student.profile.telegram_chat_id, '777001',
            "Ikkinchi odam hisobni o'ziga tortib oldi"
        )

    def test_yolgon_token_rad_etiladi(self):
        _handled, sent = self._run('/start butunlay-yolgon-token')

        self.assertIn('eskirgan', sent[0]['text'])
        self.student.refresh_from_db()
        self.assertEqual(self.student.profile.telegram_chat_id, '')

    def test_boshqa_xabarga_javob_yoq(self):
        """
        Bot suhbatdosh emas — u xabarnoma yetkazadi. Har xabarga
        javob bersa, odamlar undan savol so'rab vaqt yo'qotardi.
        """
        handled, sent = self._run('Salom, qanday o\'qish kerak?')

        self.assertFalse(handled)
        self.assertEqual(sent, [])

    def test_bosh_yangilanish_yiqitmaydi(self):
        for payload in ({}, {'message': {}}, {'message': {'chat': {}}}):
            with self.subTest(payload=payload):
                with patch('billing.telegram._post', return_value=True):
                    self.assertFalse(telegram.handle_update(payload))


@override_settings(
    TELEGRAM_BOT_TOKEN='sinov-token',
    TELEGRAM_WEBHOOK_SECRET='sinov-maxfiy-kalit',
    TELEGRAM_ADMIN_CHAT_IDS=[],
)
class WebhookTests(TestCase):
    """Webhook — production yo'li."""

    def setUp(self):
        self.student = make_user('oquvchi2')
        self.url = reverse('billing:telegram_webhook', args=['sinov-maxfiy-kalit'])

    def _post(self, url, payload):
        with patch('billing.telegram._post', return_value=True):
            return self.client.post(
                url, data=json.dumps(payload), content_type='application/json'
            )

    def test_togri_kalit_bilan_ishlaydi(self):
        link = telegram.create_link_token(self.student)
        token = link.rsplit('=', 1)[-1]

        response = self._post(self.url, update_for(f'/start {token}'))

        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.profile.telegram_chat_id, '777001')

    def test_YOLGON_KALIT_404(self):
        """
        Maxfiy manzil bo'lmasa har kim soxta `/start` yuborib
        begona hisobni o'ziga bog'lab olardi.
        """
        bad = reverse('billing:telegram_webhook', args=['yolgon'])

        response = self._post(bad, update_for('/start'))

        self.assertEqual(response.status_code, 404)

    def test_buzuq_JSON_yiqitmaydi(self):
        """
        Telegram 200 dan boshqa javob olsa, o'sha yangilanishni
        qayta-qayta yuboraveradi.
        """
        response = self.client.post(
            self.url, data='{buzuq', content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
