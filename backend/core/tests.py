from datetime import timedelta
import re
"""
1-bosqich tuzatishlarini himoya qiluvchi testlar.

Ishga tushirish:  python manage.py test core
"""

import json

from django.contrib.auth.models import User
from core import quiz_scoring
from core import password_reset as pwreset
from core.test_utils import approve_all
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Category,
    Choice,
    Lesson,
    Module,
    PasswordReset,
    Profile,
    Question,
    Quiz,
    QuizResult,
    UserProgress,
)


class BaseFixtureMixin:
    """
    Kichik, lekin to'liq kontent daraxti.

    Dars ATAYLAB `is_free=True`: bu fayldagi testlar ball hisobi, progress
    va autentifikatsiyani tekshiradi, obuna darvozasini emas. Darvoza
    `billing.tests.ContentGatingTests` da alohida sinaladi.
    """

    def build_content(self):
        self.category = Category.objects.create(name="Python", slug="python")
        self.module = Module.objects.create(category=self.category, title="Asoslar", order=1)
        self.lesson = Lesson.objects.create(
            module=self.module, title="Kirish", theory="Nazariya", order=1, is_free=True
        )
        self.quiz = Quiz.objects.create(lesson=self.lesson, title="Kirish testi", time_limit=10)

        # 2 savol, har birida 1 to'g'ri + 1 noto'g'ri variant
        self.q1 = Question.objects.create(quiz=self.quiz, text="2+2?")
        self.q1_ok = Choice.objects.create(question=self.q1, text="4", is_correct=True)
        self.q1_bad = Choice.objects.create(question=self.q1, text="5", is_correct=False)

        self.q2 = Question.objects.create(quiz=self.quiz, text="Python interpretatsiya qilinadimi?")
        self.q2_ok = Choice.objects.create(question=self.q2, text="Ha", is_correct=True)
        self.q2_bad = Choice.objects.create(question=self.q2, text="Yo'q", is_correct=False)


class QuizScoringTests(TestCase):
    """
    Ball hisoblash.

    ENDI XIZMAT FUNKSIYASI TO'G'RIDAN-TO'G'RI chaqiriladi
    (`core.quiz_scoring.score_quiz`), HTTP orqali emas. Sababi:
    tekshirilayotgan narsa — hisoblash mantig'i, u qaysi qatlamdan
    chaqirilishi ahamiyatsiz. HTTP darajasidagi tekshiruv
    `api/tests.py` da.
    """

    def setUp(self):
        category = Category.objects.create(name='Python', slug='python')
        module = Module.objects.create(category=category, title='Modul', order=1)
        lesson = Lesson.objects.create(
            module=module, title='Dars', theory='Matn', order=1, is_free=True
        )
        self.quiz = Quiz.objects.create(lesson=lesson, title='Test', is_published=True)

        self.questions = []
        self.correct = []
        for i in range(4):
            question = Question.objects.create(quiz=self.quiz, text=f'Savol {i}')
            right = Choice.objects.create(question=question, text='To\'g\'ri', is_correct=True)
            Choice.objects.create(question=question, text='Xato', is_correct=False)
            self.questions.append(question)
            self.correct.append(right)

        self.user = User.objects.create_user('talaba', password='JudaKuchliParol9')
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def _score(self, answers):
        return quiz_scoring.score_quiz(self.user, self.quiz, answers)

    def test_hammasi_togri(self):
        answers = {q.id: c.id for q, c in zip(self.questions, self.correct)}
        result = self._score(answers)

        self.assertEqual(result['score'], 100)
        self.assertEqual(result['correct'], 4)

    def test_yarmi_togri(self):
        answers = {
            self.questions[0].id: self.correct[0].id,
            self.questions[1].id: self.correct[1].id,
        }
        result = self._score(answers)

        self.assertEqual(result['score'], 50)
        self.assertEqual(result['correct'], 2)

    def test_notogri_javob_hisoblanmaydi(self):
        wrong = Choice.objects.filter(question=self.questions[0], is_correct=False).first()
        result = self._score({self.questions[0].id: wrong.id})

        self.assertEqual(result['score'], 0)

    def test_satr_kalitlar_ham_qabul_qilinadi(self):
        """JSON dan kelganda kalitlar SATR bo'ladi, formadan — son."""
        answers = {str(q.id): c.id for q, c in zip(self.questions, self.correct)}
        self.assertEqual(self._score(answers)['score'], 100)

    def test_eng_yaxshi_natija_saqlanadi(self):
        """Qayta topshirish oldingi yutuqni yo'qotmasligi kerak."""
        self._score({q.id: c.id for q, c in zip(self.questions, self.correct)})
        self._score({})

        result = QuizResult.objects.get(user=self.user, quiz=self.quiz)
        self.assertEqual(result.score_percentage, 100)
        self.assertEqual(result.attempts, 2)

    def test_boshqa_testning_tanlovi_hisobga_olinmaydi(self):
        """
        To'g'ri variantlar FAQAT shu testdan olinadi. Butun bazadan
        olinsa, boshqa testning tanlov id si ham "to'g'ri" bo'lardi.
        """
        other_lesson = Lesson.objects.create(
            module=self.quiz.lesson.module, title='Boshqa', theory='M', order=2
        )
        other_quiz = Quiz.objects.create(lesson=other_lesson, title='Boshqa test')
        other_q = Question.objects.create(quiz=other_quiz, text='Savol')
        other_correct = Choice.objects.create(question=other_q, text='Ha', is_correct=True)

        result = self._score({self.questions[0].id: other_correct.id})
        self.assertEqual(result['score'], 0)

    def test_savolsiz_test_xato_beradi(self):
        empty_lesson = Lesson.objects.create(
            module=self.quiz.lesson.module, title='Bo\'sh', theory='M', order=3
        )
        empty_quiz = Quiz.objects.create(lesson=empty_lesson, title='Bo\'sh test')

        with self.assertRaises(quiz_scoring.ScoringError):
            quiz_scoring.score_quiz(self.user, empty_quiz, {})

    def test_daraja_oshadi(self):
        self._score({q.id: c.id for q, c in zip(self.questions, self.correct)})

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.level, 2)


class VideoProtectionTests(BaseFixtureMixin, TestCase):
    """5 GB video kontent himoyalanganligi."""

    def setUp(self):
        self.build_content()
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def test_video_login_talab_qiladi(self):
        response = self.client.get(reverse('lesson_video', args=[self.lesson.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_media_url_orqali_video_berilmaydi(self):
        """/media/lesson_videos/... endi ochiq marshrut emas."""
        response = self.client.get('/media/lesson_videos/1-dars.mp4')
        self.assertNotEqual(response.status_code, 200)

    def test_videosiz_dars_404(self):
        user = User.objects.create_user(username='talaba', password='JudaKuchliParol9')
        approve_all()   # setUp dan KEYIN yaratildi — ruxsatni qayta ochamiz
        self.client.force_login(user)
        response = self.client.get(reverse('lesson_video', args=[self.lesson.id]))
        self.assertEqual(response.status_code, 404)


class PasswordResetTests(TestCase):
    """
    Parol tiklash — XIZMAT DARAJASIDA.

    Sahifalar React'da, HTTP tekshiruvi `api/tests.py` da. Bu yerda
    mantiq sinaladi: kod, muddat, urinishlar soni.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            'talaba', email='talaba@example.com', password='EskiParol12345'
        )
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def test_kod_yuboriladi_va_xeshlanadi(self):
        pwreset.request_reset('talaba@example.com')

        row = PasswordReset.objects.get(user=self.user)
        self.assertEqual(len(row.code_hash), 64, "Kod XESHLANGAN holda saqlanishi kerak")
        self.assertEqual(len(mail.outbox), 1)

    def test_javob_email_bor_yoqligini_OSHKOR_QILMAYDI(self):
        """
        Aks holda bu manzil "qaysi email ro'yxatda" degan savolga
        javob beradigan asbobga aylanardi.
        """
        found = pwreset.request_reset('talaba@example.com')
        missing = pwreset.request_reset('yoq@example.com')

        self.assertEqual(found, missing)

    def test_togri_kod_parolni_almashtiradi(self):
        code = self._request_and_read_code()
        pwreset.confirm_reset('talaba@example.com', code, 'YangiKuchliParol9')

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('YangiKuchliParol9'))

    def test_notogri_kod_rad_etiladi(self):
        self._request_and_read_code()

        with self.assertRaises(pwreset.ResetError):
            pwreset.confirm_reset('talaba@example.com', '000000', 'YangiKuchliParol9')

    def test_kod_bir_marta_ishlaydi(self):
        code = self._request_and_read_code()
        pwreset.confirm_reset('talaba@example.com', code, 'YangiKuchliParol9')

        with self.assertRaises(pwreset.ResetError):
            pwreset.confirm_reset('talaba@example.com', code, 'BoshqaParol12345')

    def test_muddati_otgan_kod_ishlamaydi(self):
        code = self._request_and_read_code()
        PasswordReset.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )

        with self.assertRaises(pwreset.ResetError):
            pwreset.confirm_reset('talaba@example.com', code, 'YangiKuchliParol9')

    def test_kop_urinishdan_keyin_kod_kuyadi(self):
        """
        MUHIM: urinishlar soni tranzaksiya orqaga qaytganda ham
        SAQLANISHI kerak — aks holda cheklov umuman ishlamasdi.
        """
        self._request_and_read_code()

        for _ in range(pwreset.MAX_ATTEMPTS):
            with self.assertRaises(pwreset.ResetError):
                pwreset.confirm_reset('talaba@example.com', '000000', 'YangiParol12345')

        row = PasswordReset.objects.get(user=self.user)
        self.assertGreaterEqual(row.attempts, pwreset.MAX_ATTEMPTS)

    def test_zaif_parol_rad_etiladi(self):
        code = self._request_and_read_code()

        with self.assertRaises(pwreset.ResetError):
            pwreset.confirm_reset('talaba@example.com', code, '12345678')

    def _request_and_read_code(self) -> str:
        """Kodni xatdan o'qib oladi — u bazada faqat xesh holida."""
        mail.outbox.clear()
        pwreset.request_reset('talaba@example.com')
        match = re.search(r'\b(\d{6})\b', mail.outbox[0].body)
        self.assertIsNotNone(match, "Xatda 6 xonali kod bo'lishi kerak")
        return match.group(1)


