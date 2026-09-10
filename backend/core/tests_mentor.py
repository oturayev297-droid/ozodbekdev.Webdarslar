"""
AI Mentor testlari.

Modelga haqiqiy so'rov YUBORILMAYDI — `_call_claude` o'rniga soxta
funksiya qo'yiladi. Testda tarmoqqa chiqish sekin, qimmat va
ishonchsiz bo'lardi.

Ishga tushirish:  python manage.py test core.tests_mentor
"""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from core.test_utils import approve_all
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import ai_mentor, mentor_knowledge
from .models import Category, Challenge, Lesson, MentorMessage, Module

FAKE_KEY = "sk-ant-test-kalit"


@override_settings(ANTHROPIC_API_KEY=FAKE_KEY, ANTHROPIC_MODEL="claude-opus-5")
class MentorBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='talaba', email='t@test.uz', password='Parol12345678'
        )
        self.client.force_login(self.user)
        # Eski sahifa o'chirilgan — mentor endi API orqali
        self.url = reverse('api:mentor_ask')
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def ask(self, question="Python'da for sikli qanday ishlaydi?", **extra):
        payload = {'question': question}
        payload.update(extra)
        return self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json'
        )


class MockModeTests(TestCase):
    """Kalit bo'sh bo'lsa sayt buzilmasligi kerak."""

    def setUp(self):
        self.user = User.objects.create_user(username='talaba', password='Parol12345678')
        self.client.force_login(self.user)
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    @override_settings(ANTHROPIC_API_KEY="")
    def test_sozlanmagan_holda_xato_bermaydi(self):
        response = self.client.post(
            reverse('api:mentor_ask'),
            data=json.dumps({'question': 'Salom'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('answer_html', data)
        self.assertTrue(data['mock'])
        self.assertIn('sozlanmagan', data['answer_html'])

    @override_settings(ANTHROPIC_API_KEY="")
    def test_mock_rejimda_yozuv_saqlanmaydi(self):
        """Kvota faqat haqiqiy so'rovlardan sanalishi kerak."""
        self.client.post(
            reverse('api:mentor_ask'),
            data=json.dumps({'question': 'Salom'}),
            content_type='application/json',
        )
        self.assertEqual(MentorMessage.objects.count(), 0)


class AskTests(MentorBase):
    @patch('core.ai_mentor._call_claude', return_value="For sikli **takrorlaydi**.")
    def test_javob_qaytaradi(self, mock_call):
        data = self.ask().json()
        self.assertIn('answer_html', data)
        self.assertFalse(data['mock'])
        self.assertIn('<strong>takrorlaydi</strong>', data['answer_html'])
        mock_call.assert_called_once()

    @patch('core.ai_mentor._call_claude', return_value="Javob")
    def test_suhbat_saqlanadi(self, _):
        self.ask("Django nima?")
        row = MentorMessage.objects.get()
        self.assertEqual(row.user, self.user)
        self.assertEqual(row.question, "Django nima?")
        self.assertEqual(row.answer, "Javob")

    def test_bosh_savol_rad_etiladi(self):
        response = self.ask("   ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(MentorMessage.objects.count(), 0)

    def test_juda_uzun_savol_rad_etiladi(self):
        response = self.ask("a" * (ai_mentor.MAX_QUESTION_LENGTH + 1))
        self.assertEqual(response.status_code, 400)

    def test_login_talab_qiladi(self):
        self.client.logout()
        response = self.ask()
        # API kirmagan odamga 403 beradi (yo'naltirish emas) —
        # frontend o'zi login sahifasiga olib boradi
        self.assertEqual(response.status_code, 403)

    def test_get_qabul_qilinmaydi(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class QuotaTests(MentorBase):
    @patch('core.ai_mentor._call_claude', return_value="Javob")
    def test_daqiqalik_cheklov(self, _):
        for _i in range(ai_mentor.MAX_PER_MINUTE):
            self.assertEqual(self.ask().status_code, 200)

        response = self.ask()
        self.assertEqual(response.status_code, 429)
        self.assertIn('tez', response.json()['detail'])

    @patch('core.ai_mentor._call_claude', return_value="Javob")
    def test_kunlik_cheklov(self, _):
        # Kunlik chegaraga yetguncha yozuvlarni to'g'ridan-to'g'ri yaratamiz
        MentorMessage.objects.bulk_create([
            MentorMessage(user=self.user, question=f"q{i}", answer="a")
            for i in range(ai_mentor.MAX_PER_DAY)
        ])
        # Daqiqalik cheklovga tushmasligi uchun ularni orqaga suramiz
        MentorMessage.objects.update(created_at=timezone.now() - timedelta(hours=2))

        response = self.ask()
        self.assertEqual(response.status_code, 429)
        self.assertIn('Kunlik', response.json()['detail'])

    @patch('core.ai_mentor._call_claude', return_value="Javob")
    def test_eski_sorovlar_hisoblanmaydi(self, _):
        MentorMessage.objects.bulk_create([
            MentorMessage(user=self.user, question=f"q{i}", answer="a")
            for i in range(ai_mentor.MAX_PER_DAY)
        ])
        MentorMessage.objects.update(created_at=timezone.now() - timedelta(days=2))

        self.assertEqual(self.ask().status_code, 200)

    @patch('core.ai_mentor._call_claude', return_value="Javob")
    def test_cheklov_foydalanuvchi_boyicha(self, _):
        """Bir o'quvchining kvotasi boshqasiga ta'sir qilmasligi kerak."""
        for _i in range(ai_mentor.MAX_PER_MINUTE):
            self.ask()
        self.assertEqual(self.ask().status_code, 429)

        other = User.objects.create_user(username='boshqa', password='Parol12345678')
        approve_all()   # setUp dan KEYIN yaratildi — ruxsatni qayta ochamiz
        self.client.force_login(other)
        self.assertEqual(self.ask().status_code, 200)


class HistoryTests(MentorBase):
    @patch('core.ai_mentor._call_claude', return_value="Javob")
    def test_tarix_serverdan_olinadi(self, _):
        self.ask("Birinchi savol")
        history = ai_mentor._history(self.user)
        self.assertEqual(history, [
            {'role': 'user', 'content': "Birinchi savol"},
            {'role': 'assistant', 'content': "Javob"},
        ])

    @patch('core.ai_mentor._call_claude', return_value="Javob")
    def test_tarix_cheklangan(self, _):
        """Cheklovsiz uzun suhbat har so'rovda qayta yuborilib, xarajat o'sardi."""
        MentorMessage.objects.bulk_create([
            MentorMessage(user=self.user, question=f"q{i}", answer=f"a{i}")
            for i in range(20)
        ])
        history = ai_mentor._history(self.user)
        self.assertEqual(len(history), ai_mentor.HISTORY_TURNS * 2)

    @patch('core.ai_mentor._call_claude', return_value="Javob")
    def test_begona_tarix_aralashmaydi(self, _):
        other = User.objects.create_user(username='boshqa', password='Parol12345678')
        MentorMessage.objects.create(user=other, question="Maxfiy", answer="Maxfiy javob")

        history = ai_mentor._history(self.user)
        self.assertEqual(history, [])


class LessonContextTests(MentorBase):
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name="Python", slug="python")
        self.module = Module.objects.create(category=self.category, title="Asoslar", order=1)
        self.free = Lesson.objects.create(
            module=self.module, title="Bepul dars", order=1, is_free=True
        )
        self.paid = Lesson.objects.create(
            module=self.module, title="Pullik dars", order=2, is_free=False
        )
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    @patch('core.ai_mentor._call_claude', return_value="Javob")
    def test_bepul_dars_konteksti_qabul_qilinadi(self, mock_call):
        self.ask(lesson_id=self.free.id)
        self.assertEqual(MentorMessage.objects.get().lesson, self.free)

    @patch('core.ai_mentor._call_claude', return_value="Javob")
    def test_qulflangan_dars_konteksti_rad_etiladi(self, mock_call):
        """
        Aks holda obunasiz o'quvchi qulflangan dars raqamini yuborib,
        model orqali uning mazmunini bilib olardi.
        """
        self.ask(lesson_id=self.paid.id)
        self.assertIsNone(MentorMessage.objects.get().lesson)

    @patch('core.ai_mentor._call_claude', return_value="Javob")
    def test_mavjud_bolmagan_dars_yiqitmaydi(self, _):
        self.assertEqual(self.ask(lesson_id=999999).status_code, 200)


class HtmlRenderTests(TestCase):
    """
    Model matni chatga `innerHTML` bilan qo'yiladi — HTML ni O'ZIMIZ
    quramiz va faqat kerakli teglarni chiqaramiz.
    """

    def test_html_qochiriladi(self):
        html = ai_mentor._to_html("<script>alert(1)</script>")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_kod_bloki(self):
        html = ai_mentor._to_html("Misol:\n```python\nprint('salom')\n```")
        self.assertIn("<pre", html)
        self.assertIn("print(&#x27;salom&#x27;)", html)

    def test_kod_ichidagi_html_qochiriladi(self):
        html = ai_mentor._to_html("```\n<img src=x onerror=alert(1)>\n```")
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)

    def test_qalin_matn(self):
        self.assertIn("<strong>muhim</strong>", ai_mentor._to_html("Bu **muhim** narsa"))

    def test_kod_ichidagi_yulduzcha_qalin_qilinmaydi(self):
        html = ai_mentor._to_html("```\na = b ** 2\n```")
        self.assertNotIn("<strong>", html)

    def test_qator_uzilishi(self):
        self.assertIn("<br>", ai_mentor._to_html("Birinchi\nIkkinchi"))


@override_settings(ANTHROPIC_API_KEY=FAKE_KEY)
class ApiErrorTests(MentorBase):
    """Model tomonidagi nosozlik foydalanuvchiga tushunarli chiqishi kerak."""

    def test_rad_etish_ushlanadi(self):
        with patch('core.ai_mentor._call_claude') as mock_call:
            mock_call.side_effect = ai_mentor.MentorError(
                "Bu savolga javob bera olmayman. Dasturlashga oid savol bering."
            )
            response = self.ask("Ob-havo qanday?")
        self.assertEqual(response.status_code, 400)
        # API xatoni `detail` da beradi (DRF ning odatiy shakli)
        self.assertIn("javob bera olmayman", response.json()['detail'])
        self.assertEqual(MentorMessage.objects.count(), 0)

    def test_tarmoq_xatosi_ushlanadi(self):
        with patch('core.ai_mentor._call_claude') as mock_call:
            mock_call.side_effect = ai_mentor.MentorError("Tarmoqda nosozlik.", status=503)
            response = self.ask()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(MentorMessage.objects.count(), 0)


class KnowledgeTests(TestCase):
    """
    Mentor bilimi: platforma qo'llanmasi va bazadan quriladigan katalog.

    Katalog har so'rovda qayta quriladi va KESHLANADI — shuning uchun u
    barqaror bo'lishi va maxfiy narsani (yechimlarni) ko'rsatmasligi shart.
    """

    def setUp(self):
        category = Category.objects.create(
            name="Python", slug="python", description="Python asoslari"
        )
        self.module = Module.objects.create(category=category, title="Asoslar", order=1)
        self.lesson = Lesson.objects.create(
            module=self.module, title="Sikllar", order=1, is_free=True,
            theory="For sikli haqida. " * 20, practice_code="for i in range(3):\n    print(i)",
        )
        Challenge.objects.create(
            language='python', title="Yig'indi", description="Vazifa",
            initial_code='', solution_code='MAXFIY_YECHIM',
            expected_output='MAXFIY_NATIJA', order=1, difficulty='Oson',
        )

    def test_katalogda_kurs_modul_va_dars_bor(self):
        text = mentor_knowledge.catalog()
        self.assertIn("## Python (/kurslar/python)", text)
        self.assertIn("### Modul: Asoslar", text)
        self.assertIn(f"[{self.lesson.id}] Sikllar (bepul, yozma matn)", text)

    def test_katalog_yechim_va_kutilgan_natijani_oshkor_qilmaydi(self):
        text = mentor_knowledge.catalog()
        self.assertIn("Yig'indi (python, Oson)", text)
        self.assertNotIn('MAXFIY_YECHIM', text)
        self.assertNotIn('MAXFIY_NATIJA', text)

    def test_katalog_barqaror(self):
        """Tartib o'zgarsa kesh har so'rovda buzilardi."""
        Lesson.objects.create(module=self.module, title="Teng tartib", order=1)
        self.assertEqual(mentor_knowledge.catalog(), mentor_knowledge.catalog())

    def test_toldiruvchi_matn_yozma_matn_hisoblanmaydi(self):
        """"Theory here..." kabi to'ldiruvchi — matn emas."""
        placeholder = Lesson.objects.create(
            module=self.module, title="Video dars", order=2, theory="Theory here..."
        )
        line = next(
            l for l in mentor_knowledge.catalog().splitlines()
            if l.startswith(f"- [{placeholder.id}]")
        )
        self.assertNotIn("yozma matn", line)

    def test_dars_konteksti_matn_va_kodni_oladi(self):
        context = ai_mentor._lesson_context(self.lesson)
        self.assertIn('"Sikllar"', context)
        self.assertIn("<dars_matni>", context)
        self.assertIn("For sikli haqida.", context)
        self.assertIn("for i in range(3):", context)

    def test_matnsiz_darsda_video_ekani_aytiladi(self):
        lesson = Lesson.objects.create(module=self.module, title="Faqat video", order=3)
        context = ai_mentor._lesson_context(lesson)
        self.assertIn("faqat videoda", context)
        self.assertNotIn("<dars_matni>", context)

    def test_uzun_matn_qisqartirilgani_ochiq_aytiladi(self):
        self.lesson.theory = "a" * (ai_mentor.MAX_LESSON_TEXT + 100)
        context = ai_mentor._lesson_context(self.lesson)
        self.assertIn("qisqartirildi", context)

    @override_settings(ANTHROPIC_API_KEY=FAKE_KEY)
    def test_bilim_ikki_keshlanadigan_system_blokida_ketadi(self):
        user = User.objects.create_user('savolchi', password='Parol12345678')
        response = MagicMock(stop_reason='end_turn')
        response.content = [MagicMock(type='text', text='Javob')]

        with patch('anthropic.Anthropic') as client_cls:
            client_cls.return_value.messages.create.return_value = response
            ai_mentor._call_claude(user, "Sertifikat qanday olinadi?", self.lesson)

        kwargs = client_cls.return_value.messages.create.call_args.kwargs
        guide, catalog = kwargs['system']
        self.assertIn("/sertifikat-tekshirish", guide['text'])
        self.assertIn("Sikllar", catalog['text'])
        self.assertEqual(guide['cache_control'], {'type': 'ephemeral'})
        self.assertEqual(catalog['cache_control'], {'type': 'ephemeral'})

        # Savol va dars matni breakpoint'lardan KEYIN — messages da
        question = kwargs['messages'][-1]['content']
        self.assertIn("Sertifikat qanday olinadi?", question)
        self.assertIn("<dars_matni>", question)
