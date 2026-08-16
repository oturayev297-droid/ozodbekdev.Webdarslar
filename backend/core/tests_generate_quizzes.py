"""
`generate_quizzes` buyrug'i testlari.

Modelga haqiqiy so'rov yuborilmaydi — `_ask_model` soxta javob qaytaradi.
Tekshirilayotgan narsa: darslarni tanlash, matn yetarliligi to'sig'i,
model javobini tekshirish va saqlash.

    python manage.py test core.tests_generate_quizzes
"""

import io
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from core.test_utils import approve_all
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, Choice, Lesson, Module, Question, Quiz

FAKE_KEY = "sk-ant-test"

LONG_THEORY = (
    "Python'da ro'yxat — bu bir nechta qiymatni saqlaydigan tuzilma. "
    "Kvadrat qavs ichida vergul bilan yoziladi. Indeks noldan boshlanadi. "
    "append() oxiriga qo'shadi, pop() o'chiradi va qaytaradi, sort() esa "
    "ro'yxatning o'zini tartiblaydi va None qaytaradi. sorted() dan farqi "
    "shundaki, sorted() yangi ro'yxat qaytaradi va aslini o'zgartirmaydi."
) * 2


def good_payload(n_questions=5, n_choices=4):
    return {
        'questions': [
            {
                'text': f"{i}-savol matni?",
                'choices': [
                    {'text': f"{i}-savol {j}-variant", 'is_correct': (j == 0)}
                    for j in range(n_choices)
                ],
            }
            for i in range(n_questions)
        ]
    }


@override_settings(ANTHROPIC_API_KEY=FAKE_KEY, ANTHROPIC_MODEL="claude-opus-5")
class BaseCommandTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Python", slug="python")
        self.module = Module.objects.create(category=self.category, title="Asoslar", order=1)
        self.rich = Lesson.objects.create(
            module=self.module, title="Ro'yxatlar", theory=LONG_THEORY, order=1
        )
        self.thin = Lesson.objects.create(
            module=self.module, title="Qisqa dars", theory="Theory here", order=2
        )
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def run_cmd(self, *args, **kwargs):
        out = io.StringIO()
        call_command('generate_quizzes', *args, stdout=out, stderr=out, **kwargs)
        return out.getvalue()


class GuardTests(BaseCommandTest):
    """To'siqlar: kalitsiz va noto'g'ri parametrlar bilan ishlamasin."""

    @override_settings(ANTHROPIC_API_KEY="")
    def test_kalitsiz_ishlamaydi(self):
        with self.assertRaises(CommandError) as ctx:
            self.run_cmd()
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))

    def test_notogri_savol_soni(self):
        for bad in (0, 21):
            with self.subTest(n=bad):
                with self.assertRaises(CommandError):
                    self.run_cmd('--questions', str(bad))

    def test_notogri_variant_soni(self):
        for bad in (1, 7):
            with self.subTest(n=bad):
                with self.assertRaises(CommandError):
                    self.run_cmd('--choices', str(bad))

    def test_mavjud_bolmagan_yonalish(self):
        with self.assertRaises(CommandError) as ctx:
            self.run_cmd('--category', 'kotlin')
        self.assertIn("kotlin", str(ctx.exception))

    def test_mavjud_bolmagan_dars(self):
        with self.assertRaises(CommandError):
            self.run_cmd('--lesson-id', '999999')

    def test_mavjud_bolmagan_papka(self):
        with self.assertRaises(CommandError):
            self.run_cmd('--notes-dir', '/bunday/papka/yoq')


class ThinContentTests(BaseCommandTest):
    """
    Eng muhim to'siq: matn yetarli bo'lmasa generatsiya QILINMAYDI.

    Bu platformada darslarning mazmuni videoda, `theory` da esa bir necha
    so'z. Shunday darsdan savol yozilsa, o'quvchi videoda ko'rmagan
    narsasidan imtihon topshirardi.
    """

    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_qisqa_dars_otkazib_yuboriladi(self, mock_ask):
        mock_ask.return_value = (good_payload(), (100, 200))
        output = self.run_cmd('--lesson-id', str(self.thin.id))

        mock_ask.assert_not_called()
        self.assertIn("O'TKAZIB YUBORILDI", output)
        self.assertFalse(Quiz.objects.filter(lesson=self.thin).exists())

    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_allow_thin_majburlaydi(self, mock_ask):
        mock_ask.return_value = (good_payload(), (100, 200))
        self.run_cmd('--lesson-id', str(self.thin.id), '--allow-thin')

        mock_ask.assert_called_once()
        self.assertTrue(Quiz.objects.filter(lesson=self.thin).exists())

    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_notes_dir_theory_dan_ustun(self, mock_ask):
        mock_ask.return_value = (good_payload(), (100, 200))

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / f"{self.thin.id}.txt").write_text(LONG_THEORY, encoding='utf-8')
            self.run_cmd('--lesson-id', str(self.thin.id), '--notes-dir', tmp)

        mock_ask.assert_called_once()
        # Modelga aynan fayldagi matn borganini tekshiramiz
        sent_text = mock_ask.call_args[0][1]
        self.assertIn("sorted()", sent_text)

    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_md_kengaytmasi_ham_ishlaydi(self, mock_ask):
        mock_ask.return_value = (good_payload(), (100, 200))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / f"{self.thin.id}.md").write_text(LONG_THEORY, encoding='utf-8')
            self.run_cmd('--lesson-id', str(self.thin.id), '--notes-dir', tmp)
        mock_ask.assert_called_once()

    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_html_teglari_tozalanadi(self, mock_ask):
        mock_ask.return_value = (good_payload(), (100, 200))
        self.rich.theory = "<p><b>Ro'yxat</b> haqida</p>" + LONG_THEORY
        self.rich.save()

        self.run_cmd('--lesson-id', str(self.rich.id))
        sent_text = mock_ask.call_args[0][1]
        self.assertNotIn("<b>", sent_text)
        self.assertIn("Ro'yxat", sent_text)


class SelectionTests(BaseCommandTest):
    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_testi_bor_dars_otkazib_yuboriladi(self, mock_ask):
        mock_ask.return_value = (good_payload(), (100, 200))
        Quiz.objects.create(lesson=self.rich, title="Mavjud test")

        self.run_cmd('--category', 'python')
        mock_ask.assert_not_called()

    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_overwrite_qayta_yozadi(self, mock_ask):
        mock_ask.return_value = (good_payload(), (100, 200))
        old = Quiz.objects.create(lesson=self.rich, title="Eski test")
        Question.objects.create(quiz=old, text="Eski savol")

        self.run_cmd('--lesson-id', str(self.rich.id), '--overwrite')

        quiz = Quiz.objects.get(lesson=self.rich)
        self.assertNotEqual(quiz.pk, old.pk, "Eski test butunlay almashtirilishi kerak")
        self.assertFalse(Question.objects.filter(text="Eski savol").exists())

    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_limit_hurmat_qilinadi(self, mock_ask):
        mock_ask.return_value = (good_payload(), (100, 200))
        for i in range(5):
            Lesson.objects.create(
                module=self.module, title=f"Dars {i}", theory=LONG_THEORY, order=10 + i
            )

        self.run_cmd('--category', 'python', '--limit', '2')
        self.assertEqual(mock_ask.call_count, 2)


class ValidationTests(BaseCommandTest):
    """
    Sxema shaklni kafolatlaydi, MA'NONI emas. Yaroqsiz test
    saqlanmasligi kerak — admin uni tuzatishdan ko'ra qayta
    generatsiya qilgani osonroq.
    """

    def _run_with(self, payload):
        with patch(
            'core.management.commands.generate_quizzes.Command._ask_model',
            return_value=(payload, (100, 200)),
        ):
            return self.run_cmd('--lesson-id', str(self.rich.id))

    def test_ikkita_togri_javob_rad_etiladi(self):
        payload = good_payload()
        payload['questions'][0]['choices'][1]['is_correct'] = True

        output = self._run_with(payload)
        self.assertIn("YAROQSIZ", output)
        self.assertIn("2 ta to'g'ri javob", output)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_togri_javobsiz_rad_etiladi(self):
        payload = good_payload()
        for c in payload['questions'][0]['choices']:
            c['is_correct'] = False

        output = self._run_with(payload)
        self.assertIn("YAROQSIZ", output)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_variant_soni_notogri_rad_etiladi(self):
        payload = good_payload(n_choices=3)  # 4 kutilyapti
        output = self._run_with(payload)
        self.assertIn("YAROQSIZ", output)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_takroriy_variant_rad_etiladi(self):
        payload = good_payload()
        payload['questions'][0]['choices'][1]['text'] = \
            payload['questions'][0]['choices'][0]['text']

        output = self._run_with(payload)
        self.assertIn("takroriy", output)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_bosh_variant_rad_etiladi(self):
        payload = good_payload()
        payload['questions'][0]['choices'][2]['text'] = "   "

        output = self._run_with(payload)
        self.assertIn("YAROQSIZ", output)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_bosh_savol_matni_rad_etiladi(self):
        payload = good_payload()
        payload['questions'][1]['text'] = ""

        output = self._run_with(payload)
        self.assertIn("YAROQSIZ", output)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_bosh_royxat_xato_emas(self):
        """Model material yetarli emas desa, bu XATO emas — o'tkazib yuboriladi."""
        output = self._run_with({'questions': []})
        self.assertIn("BO'SH", output)
        self.assertEqual(Quiz.objects.count(), 0)


class SaveTests(BaseCommandTest):
    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_qoralama_sifatida_saqlanadi(self, mock_ask):
        mock_ask.return_value = (good_payload(), (100, 200))
        self.run_cmd('--lesson-id', str(self.rich.id))

        quiz = Quiz.objects.get(lesson=self.rich)
        self.assertFalse(quiz.is_published, "Tekshirilmagan test nashrda bo'lmasligi kerak")
        self.assertTrue(quiz.is_generated)
        self.assertEqual(quiz.questions.count(), 5)

        for question in quiz.questions.all():
            self.assertEqual(question.choices.count(), 4)
            self.assertEqual(question.choices.filter(is_correct=True).count(), 1)

    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_dry_run_saqlamaydi(self, mock_ask):
        mock_ask.return_value = (good_payload(), (100, 200))
        output = self.run_cmd('--lesson-id', str(self.rich.id), '--dry-run')

        self.assertIn("dry-run", output)
        self.assertEqual(Quiz.objects.count(), 0)

    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_savol_soni_sozlanadi(self, mock_ask):
        mock_ask.return_value = (good_payload(n_questions=8, n_choices=3), (100, 200))
        self.run_cmd('--lesson-id', str(self.rich.id), '--questions', '8', '--choices', '3')

        quiz = Quiz.objects.get(lesson=self.rich)
        self.assertEqual(quiz.questions.count(), 8)
        self.assertEqual(quiz.questions.first().choices.count(), 3)

    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_api_xatosi_yiqitmaydi(self, mock_ask):
        mock_ask.side_effect = RuntimeError("API ishlamayapti")
        output = self.run_cmd('--lesson-id', str(self.rich.id))

        self.assertIn("XATO", output)
        self.assertEqual(Quiz.objects.count(), 0)

    @patch('core.management.commands.generate_quizzes.Command._ask_model')
    def test_chiqish_windows_konsolida_yiqilmaydi(self, mock_ask):
        """
        Windows konsoli cp1251 da ishlaydi va unda "✓" (U+2713) yo'q —
        buyruq UnicodeEncodeError bilan yiqilardi. Test runner chiqishni
        StringIO ga olgani uchun oddiy test buni sezmaydi, shuning uchun
        matnni ATAYLAB cp1251 ga kodlab ko'ramiz.
        """
        mock_ask.return_value = (good_payload(), (100, 200))
        output = self.run_cmd('--lesson-id', str(self.rich.id), '--dry-run')

        try:
            output.encode('cp1251')
        except UnicodeEncodeError as exc:
            self.fail(
                f"Chiqishda cp1251 ga sig'maydigan belgi bor: {exc.object[exc.start:exc.end]!r}"
            )


class DraftVisibilityTests(TestCase):
    """Qoralama test o'quvchiga UMUMAN ko'rinmasligi kerak."""

    def setUp(self):
        self.category = Category.objects.create(name="Python", slug="python")
        self.module = Module.objects.create(category=self.category, title="Asoslar", order=1)
        self.lesson = Lesson.objects.create(
            module=self.module, title="Dars", order=1, is_free=True
        )
        self.draft = Quiz.objects.create(
            lesson=self.lesson, title="Qoralama test",
            is_published=False, is_generated=True,
        )
        question = Question.objects.create(quiz=self.draft, text="Savol?")
        Choice.objects.create(question=question, text="Ha", is_correct=True)
        Choice.objects.create(question=question, text="Yo'q", is_correct=False)

        self.student = User.objects.create_user(username='talaba', password='Parol12345678')
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def test_oquvchi_royxatda_kormaydi(self):
        self.client.force_login(self.student)
        # Testlar ro'yxati endi API da
        response = self.client.get(reverse('api:quizzes'))
        self.assertNotContains(response, "Qoralama test")

    def test_oquvchi_ocholmaydi(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('api:quiz_detail', args=[self.draft.id]))
        self.assertEqual(response.status_code, 404)

    def test_oquvchi_topshirolmaydi(self):
        import json
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('api:quiz_submit', args=[self.draft.id]),
            data=json.dumps({'answers': {}}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_xodim_koradi(self):
        """Admin aynan tekshirish uchun ochadi."""
        staff = User.objects.create_user(
            username='admin', password='Parol12345678', is_staff=True
        )
        self.client.force_login(staff)
        self.assertEqual(
            self.client.get(reverse('api:quiz_detail', args=[self.draft.id])).status_code, 200
        )

    def test_nashr_qilingach_korinadi(self):
        self.draft.is_published = True
        self.draft.save()

        self.client.force_login(self.student)
        self.assertEqual(
            self.client.get(reverse('api:quiz_detail', args=[self.draft.id])).status_code, 200
        )
