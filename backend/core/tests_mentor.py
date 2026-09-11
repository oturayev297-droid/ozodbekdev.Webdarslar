"""
AI Mentor testlari.

Modelga haqiqiy so'rov YUBORILMAYDI — `_call_model` o'rniga soxta
funksiya qo'yiladi. Testda tarmoqqa chiqish sekin, qimmat va
ishonchsiz bo'lardi.

Ishga tushirish:  python manage.py test core.tests_mentor
"""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import httpx
import openai

from django.contrib.auth.models import User
from core.test_utils import approve_all
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import ai_mentor, mentor_knowledge
from .models import Category, Challenge, Lesson, MentorMessage, Module

FAKE_KEY = "gemini-test-kalit"


@override_settings(GEMINI_API_KEY=FAKE_KEY, GEMINI_MODEL="gemini-2.5-flash")
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

    @override_settings(GEMINI_API_KEY="")
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

    @override_settings(GEMINI_API_KEY="")
    def test_mock_rejimda_yozuv_saqlanmaydi(self):
        """Kvota faqat haqiqiy so'rovlardan sanalishi kerak."""
        self.client.post(
            reverse('api:mentor_ask'),
            data=json.dumps({'question': 'Salom'}),
            content_type='application/json',
        )
        self.assertEqual(MentorMessage.objects.count(), 0)


class AskTests(MentorBase):
    @patch('core.ai_mentor._call_model', return_value="For sikli **takrorlaydi**.")
    def test_javob_qaytaradi(self, mock_call):
        data = self.ask().json()
        self.assertIn('answer_html', data)
        self.assertFalse(data['mock'])
        self.assertIn('<strong>takrorlaydi</strong>', data['answer_html'])
        mock_call.assert_called_once()

    @patch('core.ai_mentor._call_model', return_value="Javob")
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
    @patch('core.ai_mentor._call_model', return_value="Javob")
    def test_daqiqalik_cheklov(self, _):
        for _i in range(ai_mentor.MAX_PER_MINUTE):
            self.assertEqual(self.ask().status_code, 200)

        response = self.ask()
        self.assertEqual(response.status_code, 429)
        self.assertIn('tez', response.json()['detail'])

    @patch('core.ai_mentor._call_model', return_value="Javob")
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

    @patch('core.ai_mentor._call_model', return_value="Javob")
    def test_eski_sorovlar_hisoblanmaydi(self, _):
        MentorMessage.objects.bulk_create([
            MentorMessage(user=self.user, question=f"q{i}", answer="a")
            for i in range(ai_mentor.MAX_PER_DAY)
        ])
        MentorMessage.objects.update(created_at=timezone.now() - timedelta(days=2))

        self.assertEqual(self.ask().status_code, 200)

    @patch('core.ai_mentor._call_model', return_value="Javob")
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
    @patch('core.ai_mentor._call_model', return_value="Javob")
    def test_tarix_serverdan_olinadi(self, _):
        self.ask("Birinchi savol")
        history = ai_mentor._history(self.user)
        self.assertEqual(history, [
            {'role': 'user', 'content': "Birinchi savol"},
            {'role': 'assistant', 'content': "Javob"},
        ])

    @patch('core.ai_mentor._call_model', return_value="Javob")
    def test_tarix_cheklangan(self, _):
        """Cheklovsiz uzun suhbat har so'rovda qayta yuborilib, xarajat o'sardi."""
        MentorMessage.objects.bulk_create([
            MentorMessage(user=self.user, question=f"q{i}", answer=f"a{i}")
            for i in range(20)
        ])
        history = ai_mentor._history(self.user)
        self.assertEqual(len(history), ai_mentor.HISTORY_TURNS * 2)

    @patch('core.ai_mentor._call_model', return_value="Javob")
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

    @patch('core.ai_mentor._call_model', return_value="Javob")
    def test_bepul_dars_konteksti_qabul_qilinadi(self, mock_call):
        self.ask(lesson_id=self.free.id)
        self.assertEqual(MentorMessage.objects.get().lesson, self.free)

    @patch('core.ai_mentor._call_model', return_value="Javob")
    def test_qulflangan_dars_konteksti_rad_etiladi(self, mock_call):
        """
        Aks holda obunasiz o'quvchi qulflangan dars raqamini yuborib,
        model orqali uning mazmunini bilib olardi.
        """
        self.ask(lesson_id=self.paid.id)
        self.assertIsNone(MentorMessage.objects.get().lesson)

    @patch('core.ai_mentor._call_model', return_value="Javob")
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


@override_settings(GEMINI_API_KEY=FAKE_KEY)
class ApiErrorTests(MentorBase):
    """Model tomonidagi nosozlik foydalanuvchiga tushunarli chiqishi kerak."""

    def test_rad_etish_ushlanadi(self):
        with patch('core.ai_mentor._call_model') as mock_call:
            mock_call.side_effect = ai_mentor.MentorError(
                "Bu savolga javob bera olmayman. Dasturlashga oid savol bering."
            )
            response = self.ask("Ob-havo qanday?")
        self.assertEqual(response.status_code, 400)
        # API xatoni `detail` da beradi (DRF ning odatiy shakli)
        self.assertIn("javob bera olmayman", response.json()['detail'])
        self.assertEqual(MentorMessage.objects.count(), 0)

    def test_tarmoq_xatosi_ushlanadi(self):
        with patch('core.ai_mentor._call_model') as mock_call:
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

    def test_tizim_korsatmasi_barqaror_tartibda(self):
        """O'zgarmas qism birinchi, katalog keyin — kesh uchun."""
        prompt = ai_mentor._system_prompt()
        self.assertTrue(prompt.startswith(ai_mentor.SYSTEM_PROMPT))
        self.assertLess(prompt.index("/sertifikat-tekshirish"), prompt.index("Sikllar"))
        self.assertEqual(prompt, ai_mentor._system_prompt())


def _completion(text='Javob', finish_reason='stop'):
    """`chat.completions.create` javobining soxta nusxasi."""
    choice = MagicMock(finish_reason=finish_reason)
    choice.message.content = text
    return MagicMock(choices=[choice])


def _status_error(cls, status_code):
    request = httpx.Request('POST', ai_mentor.GEMINI_BASE_URL + 'chat/completions')
    return cls("xato", response=httpx.Response(status_code, request=request), body=None)


@override_settings(GEMINI_API_KEY=FAKE_KEY, GEMINI_MODEL="gemini-2.5-flash")
class GeminiCallTests(TestCase):
    """
    Gemini'ga so'rov — `openai` kutubxonasi mock qilinadi, tarmoqqa
    chiqilmaydi.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            'maxfiy_login', email='maxfiy@pochta.uz', password='Parol12345678'
        )
        profile = self.user.profile
        profile.full_name = "Maxfiyjon Ismov"
        profile.save(update_fields=['full_name'])

        category = Category.objects.create(name="Python", slug="python")
        module = Module.objects.create(category=category, title="Asoslar", order=1)
        self.lesson = Lesson.objects.create(
            module=module, title="Sikllar", order=1, is_free=True,
            theory="For sikli haqida. " * 20,
        )

    def _call(self, side_effect=None, result=None):
        with patch('openai.OpenAI') as client_cls:
            create = client_cls.return_value.chat.completions.create
            if side_effect is not None:
                create.side_effect = side_effect
            else:
                create.return_value = result or _completion()
            try:
                return ai_mentor._call_model(self.user, "For sikli nima?", self.lesson)
            finally:
                self.client_kwargs = client_cls.call_args.kwargs if client_cls.call_args else {}
                self.create_kwargs = create.call_args.kwargs if create.call_args else {}

    def test_sorov_gemini_ga_ketadi(self):
        self.assertEqual(self._call(result=_completion("For — sikl.")), "For — sikl.")

        self.assertEqual(self.client_kwargs['base_url'], ai_mentor.GEMINI_BASE_URL)
        self.assertEqual(self.client_kwargs['api_key'], FAKE_KEY)
        self.assertEqual(self.client_kwargs['max_retries'], 0)
        self.assertLess(self.client_kwargs['timeout'], 120, "gunicorn --timeout dan qisqa")
        self.assertEqual(self.create_kwargs['model'], "gemini-2.5-flash")

        messages = self.create_kwargs['messages']
        self.assertEqual(messages[0]['role'], 'system')
        self.assertIn("FAQAT o'zbek tilida", messages[0]['content'])
        self.assertIn("/sertifikat-tekshirish", messages[0]['content'])
        self.assertIn("Sikllar", messages[0]['content'])
        self.assertEqual(messages[-1]['role'], 'user')
        self.assertIn("For sikli nima?", messages[-1]['content'])
        self.assertIn("<dars_matni>", messages[-1]['content'])

    def test_ism_login_va_email_yuborilmaydi(self):
        MentorMessage.objects.create(user=self.user, question="Oldingi savol", answer="Javob")

        self._call()

        payload = json.dumps([self.client_kwargs, self.create_kwargs], default=str)
        for secret in ("maxfiy_login", "maxfiy@pochta.uz", "Maxfiyjon", str(self.user.pk) + ":"):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, payload)
        # Tarix esa ketadi — faqat matni
        self.assertIn("Oldingi savol", payload)

    def test_429_band_xabari(self):
        with self.assertLogs('core.ai_mentor', level='WARNING'):
            with self.assertRaises(ai_mentor.MentorError) as ctx:
                self._call(side_effect=_status_error(openai.RateLimitError, 429))

        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(ctx.exception.message, "Mentor band, 10 soniyadan keyin urinib ko'ring.")
        self.assertEqual(ctx.exception.retry_after, 10)

    def test_429_api_orqali_json_va_retry_after(self):
        self.client.force_login(self.user)
        approve_all()

        with patch('openai.OpenAI') as client_cls:
            client_cls.return_value.chat.completions.create.side_effect = (
                _status_error(openai.RateLimitError, 429)
            )
            response = self.client.post(
                reverse('api:mentor_ask'),
                data=json.dumps({'question': 'For nima?'}),
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['detail'], ai_mentor.BUSY_MESSAGE)
        self.assertEqual(response['Retry-After'], '10')
        self.assertEqual(MentorMessage.objects.count(), 0, "kvotaga sanalmasin")

    def test_server_xatosi_503_va_loglanadi(self):
        with self.assertLogs('core.ai_mentor', level='ERROR'):
            with self.assertRaises(ai_mentor.MentorError) as ctx:
                self._call(side_effect=_status_error(openai.InternalServerError, 500))
        self.assertEqual(ctx.exception.status, 503)

    def test_aloqa_xatosi_503(self):
        request = httpx.Request('POST', ai_mentor.GEMINI_BASE_URL)
        with self.assertLogs('core.ai_mentor', level='ERROR'):
            with self.assertRaises(ai_mentor.MentorError) as ctx:
                self._call(side_effect=openai.APIConnectionError(request=request))
        self.assertEqual(ctx.exception.status, 503)

    def test_timeout_503(self):
        request = httpx.Request('POST', ai_mentor.GEMINI_BASE_URL)
        with self.assertLogs('core.ai_mentor', level='ERROR'):
            with self.assertRaises(ai_mentor.MentorError) as ctx:
                self._call(side_effect=openai.APITimeoutError(request=request))
        self.assertEqual(ctx.exception.status, 503)

    def test_kutilmagan_xato_processni_yiqitmaydi(self):
        with self.assertLogs('core.ai_mentor', level='ERROR'):
            with self.assertRaises(ai_mentor.MentorError) as ctx:
                self._call(side_effect=ValueError("kutilmagan"))
        self.assertEqual(ctx.exception.status, 503)

    def test_buzuq_javob_processni_yiqitmaydi(self):
        with self.assertLogs('core.ai_mentor', level='ERROR'):
            with self.assertRaises(ai_mentor.MentorError) as ctx:
                self._call(result=MagicMock(choices=[object()]))
        self.assertEqual(ctx.exception.status, 503)

    def test_xavfsizlik_filtri_rad_etadi(self):
        with self.assertRaises(ai_mentor.MentorError) as ctx:
            self._call(result=_completion(None, finish_reason='content_filter'))
        self.assertEqual(ctx.exception.status, 400)

    def test_bosh_javob_503(self):
        with self.assertRaises(ai_mentor.MentorError) as ctx:
            self._call(result=_completion(""))
        self.assertEqual(ctx.exception.status, 503)
