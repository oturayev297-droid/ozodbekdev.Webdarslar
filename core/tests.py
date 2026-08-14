"""
1-bosqich tuzatishlarini himoya qiluvchi testlar.

Ishga tushirish:  python manage.py test core
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    Category,
    Choice,
    Lesson,
    Module,
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


class AuthRequiredTests(BaseFixtureMixin, TestCase):
    """Kontent sahifalari tizimga kirmasdan ochilmasligi kerak."""

    def setUp(self):
        self.build_content()

    def test_kontent_sahifalari_login_talab_qiladi(self):
        protected = [
            reverse('lessons'),
            reverse('dashboard'),
            reverse('editor'),
            reverse('projects'),
            reverse('quizzes'),
            reverse('quiz_detail', args=[self.quiz.id]),
            reverse('profile'),
            reverse('lesson_video', args=[self.lesson.id]),
        ]
        for url in protected:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn('/login/', response['Location'])

    def test_landing_ochiq(self):
        self.assertEqual(self.client.get(reverse('landing')).status_code, 200)


class QuizScoringTests(BaseFixtureMixin, TestCase):
    """Ball SERVERDA hisoblanishi va soxtalashtirilmasligi kerak."""

    def setUp(self):
        self.build_content()
        self.user = User.objects.create_user(username='talaba', password='JudaKuchliParol9')
        self.client.force_login(self.user)
        self.url = reverse('submit_quiz', args=[self.quiz.id])

    def _submit(self, answers):
        return self.client.post(
            self.url, data=json.dumps({'answers': answers}), content_type='application/json'
        )

    def test_hammasi_togri_100_foiz(self):
        response = self._submit({str(self.q1.id): self.q1_ok.id, str(self.q2.id): self.q2_ok.id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['score'], 100)
        self.assertEqual(data['correct'], 2)
        self.assertEqual(data['total'], 2)

    def test_yarmi_togri_50_foiz(self):
        data = self._submit({str(self.q1.id): self.q1_ok.id, str(self.q2.id): self.q2_bad.id}).json()
        self.assertEqual(data['score'], 50)

    def test_hammasi_notogri_0_foiz(self):
        data = self._submit({str(self.q1.id): self.q1_bad.id, str(self.q2.id): self.q2_bad.id}).json()
        self.assertEqual(data['score'], 0)

    def test_klient_yuborgan_score_eiborga_olinmaydi(self):
        """Eski zaiflik: {"score": 100} yuborib 100% olish. Endi ishlamaydi."""
        response = self.client.post(
            self.url, data=json.dumps({'score': 100}), content_type='application/json'
        )
        self.assertEqual(response.json()['score'], 0)
        self.assertEqual(QuizResult.objects.get(user=self.user).score_percentage, 0)

    def test_boshqa_testning_varianti_hisoblanmaydi(self):
        other_lesson = Lesson.objects.create(
            module=self.module, title="Boshqa", order=2, is_free=True
        )
        other_quiz = Quiz.objects.create(lesson=other_lesson, title="Boshqa test")
        other_q = Question.objects.create(quiz=other_quiz, text="?")
        other_ok = Choice.objects.create(question=other_q, text="ha", is_correct=True)

        data = self._submit({str(self.q1.id): other_ok.id, str(self.q2.id): other_ok.id}).json()
        self.assertEqual(data['score'], 0)

    def test_javoblar_html_da_ochiq_turmaydi(self):
        response = self.client.get(reverse('quiz_detail', args=[self.quiz.id]))
        self.assertNotContains(response, 'data-is-correct')

    def test_eng_yaxshi_natija_saqlanadi(self):
        self._submit({str(self.q1.id): self.q1_ok.id, str(self.q2.id): self.q2_ok.id})
        self._submit({str(self.q1.id): self.q1_bad.id, str(self.q2.id): self.q2_bad.id})

        result = QuizResult.objects.get(user=self.user, quiz=self.quiz)
        self.assertEqual(result.score_percentage, 100)
        self.assertEqual(result.attempts, 2)

    def test_level_oshishi_togri_xabar_qiladi(self):
        data = self._submit({str(self.q1.id): self.q1_ok.id, str(self.q2.id): self.q2_ok.id}).json()
        self.assertTrue(data['leveled_up'])
        self.assertEqual(data['new_level'], 2)
        self.assertEqual(Profile.objects.get(user=self.user).level, 2)

        # Ikkinchi urinishda level o'zgarmaydi -> leveled_up False
        again = self._submit({str(self.q1.id): self.q1_ok.id, str(self.q2.id): self.q2_ok.id}).json()
        self.assertFalse(again['leveled_up'])

    def test_get_soro_qabul_qilinmaydi(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class LessonProgressTests(BaseFixtureMixin, TestCase):
    """Darsni tugatish endpointi va progress statistikasi."""

    def setUp(self):
        self.build_content()
        self.user = User.objects.create_user(username='talaba', password='JudaKuchliParol9')
        self.client.force_login(self.user)

    def test_darsni_tugatish_yozuv_yaratadi(self):
        url = reverse('complete_lesson', args=[self.lesson.id])
        data = self.client.post(url).json()

        self.assertTrue(data['success'])
        self.assertEqual(data['total_completed'], 1)

        progress = UserProgress.objects.get(user=self.user, lesson=self.lesson)
        self.assertTrue(progress.is_completed)
        self.assertIsNotNone(progress.completed_at)

    def test_ikki_marta_bosish_dublikat_yaratmaydi(self):
        url = reverse('complete_lesson', args=[self.lesson.id])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(UserProgress.objects.filter(user=self.user).count(), 1)

    def test_dashboard_progressni_korsatadi(self):
        self.client.post(reverse('complete_lesson', args=[self.lesson.id]))
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['completed_lessons_count'], 1)

    def test_darslar_sahifasi_real_holatni_beradi(self):
        self.client.post(reverse('complete_lesson', args=[self.lesson.id]))
        response = self.client.get(reverse('lessons'))
        course_data = json.loads(response.context['course_data_json'])
        self.assertEqual(course_data['python']['completedLessons'], 1)
        self.assertTrue(course_data['python']['lessons'][0]['completed'])

    def test_mavjud_bolmagan_dars_404(self):
        self.assertEqual(self.client.post(reverse('complete_lesson', args=[99999])).status_code, 404)


class VideoProtectionTests(BaseFixtureMixin, TestCase):
    """5 GB video kontent himoyalanganligi."""

    def setUp(self):
        self.build_content()

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
        self.client.force_login(user)
        response = self.client.get(reverse('lesson_video', args=[self.lesson.id]))
        self.assertEqual(response.status_code, 404)


class RegistrationTests(TestCase):
    """Parol validatsiyasi haqiqatan ishlashi kerak."""

    def setUp(self):
        self.url = reverse('register')

    def _post(self, **kwargs):
        payload = {
            'username': 'yangi',
            'email': 'yangi@test.uz',
            'password': 'JudaKuchliParol9',
            'password2': 'JudaKuchliParol9',
            'full_name': 'Yangi Talaba',
        }
        payload.update(kwargs)
        return self.client.post(self.url, payload)

    def test_togri_malumot_bilan_royxatdan_otadi(self):
        response = self._post()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='yangi').exists())
        self.assertTrue(Profile.objects.filter(user__username='yangi').exists())

    def test_qisqa_parol_qabul_qilinmaydi(self):
        response = self._post(password='123', password2='123')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='yangi').exists())

    def test_faqat_raqamli_parol_qabul_qilinmaydi(self):
        response = self._post(password='84726194', password2='84726194')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='yangi').exists())

    def test_mos_kelmagan_parollar_rad_etiladi(self):
        response = self._post(password2='BoshqaParol99')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='yangi').exists())

    def test_takroriy_username_rad_etiladi(self):
        User.objects.create_user(username='yangi', password='JudaKuchliParol9')
        self._post()
        self.assertEqual(User.objects.filter(username='yangi').count(), 1)

    def test_takroriy_email_rad_etiladi(self):
        User.objects.create_user(username='eski', email='yangi@test.uz', password='JudaKuchliParol9')
        self._post()
        self.assertFalse(User.objects.filter(username='yangi').exists())


class EditorTests(BaseFixtureMixin, TestCase):
    def setUp(self):
        self.build_content()
        self.user = User.objects.create_user(username='talaba', password='JudaKuchliParol9')
        self.client.force_login(self.user)

    def test_mavjud_bolmagan_challenge_404_beradi(self):
        """Avval 500 xato qaytarardi."""
        response = self.client.get(reverse('editor_detail', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_yechim_html_da_ochiq_turmaydi(self):
        from .models import Challenge
        Challenge.objects.create(
            title="Test", description="d", initial_code="x", solution_code="MAXFIY_YECHIM_123"
        )
        response = self.client.get(reverse('editor'))
        self.assertNotContains(response, 'MAXFIY_YECHIM_123')


class LogoutTests(TestCase):
    def test_logout_faqat_post_bilan(self):
        User.objects.create_user(username='talaba', password='JudaKuchliParol9')
        self.client.login(username='talaba', password='JudaKuchliParol9')

        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertEqual(self.client.post(reverse('logout')).status_code, 302)


class PasswordResetTests(TestCase):
    """
    Parolni tiklash: xeshlangan kod, bir martalik, urinishlar cheklovi,
    enumeratsiyaga qarshi bir xil javob.
    """

    def setUp(self):
        from django.core import mail
        self.mail = mail
        self.user = User.objects.create_user(
            username='talaba', email='talaba@test.uz', password='EskiParol12345'
        )
        mail.outbox = []

    def _get_code(self):
        """Yuborilgan xatdan kodni ajratib oladi."""
        import re
        body = self.mail.outbox[-1].body
        return re.search(r'\b(\d{6})\b', body).group(1)

    # ── Kod so'rash ──

    def test_kod_yuboriladi(self):
        from core import password_reset as pw
        pw.request_reset('talaba@test.uz')
        self.assertEqual(len(self.mail.outbox), 1)
        self.assertIn('talaba@test.uz', self.mail.outbox[0].to)
        self.assertRegex(self.mail.outbox[0].body, r'\b\d{6}\b')

    def test_kod_bazada_ochiq_saqlanmaydi(self):
        from core import password_reset as pw
        from core.models import PasswordReset
        pw.request_reset('talaba@test.uz')
        code = self._get_code()

        record = PasswordReset.objects.get()
        self.assertNotEqual(record.code_hash, code)
        self.assertEqual(len(record.code_hash), 64)  # SHA-256
        self.assertEqual(record.code_hash, pw.hash_code(code))

    def test_mavjud_bolmagan_email_bir_xil_javob(self):
        """ANTI-ENUMERATSIYA: javob farq qilmasligi kerak."""
        from core import password_reset as pw
        a = pw.request_reset('talaba@test.uz')
        b = pw.request_reset('yoq@test.uz')
        self.assertEqual(a, b)
        # Lekin mavjud bo'lmaganga xat ketmaydi
        self.assertEqual(len(self.mail.outbox), 1)

    def test_yangi_kod_eskisini_bekor_qiladi(self):
        from core import password_reset as pw
        pw.request_reset('talaba@test.uz')
        old_code = self._get_code()
        pw.request_reset('talaba@test.uz')

        with self.assertRaises(pw.ResetError):
            pw.confirm_reset('talaba@test.uz', old_code, 'YangiParol12345')

    # ── Kodni ishlatish ──

    def test_togri_kod_parolni_yangilaydi(self):
        from core import password_reset as pw
        pw.request_reset('talaba@test.uz')
        pw.confirm_reset('talaba@test.uz', self._get_code(), 'YangiParol12345')

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('YangiParol12345'))
        self.assertFalse(self.user.check_password('EskiParol12345'))

    def test_kod_bir_marta_ishlaydi(self):
        from core import password_reset as pw
        pw.request_reset('talaba@test.uz')
        code = self._get_code()
        pw.confirm_reset('talaba@test.uz', code, 'YangiParol12345')

        with self.assertRaises(pw.ResetError):
            pw.confirm_reset('talaba@test.uz', code, 'BoshqaParol9999')

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('YangiParol12345'))

    def test_notogri_kod_rad_etiladi(self):
        from core import password_reset as pw
        pw.request_reset('talaba@test.uz')
        with self.assertRaises(pw.ResetError):
            pw.confirm_reset('talaba@test.uz', '000000', 'YangiParol12345')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('EskiParol12345'))

    def test_besh_urinishdan_keyin_kod_kuyadi(self):
        from core import password_reset as pw
        pw.request_reset('talaba@test.uz')
        code = self._get_code()

        wrong = '999999' if code != '999999' else '111111'
        for _ in range(pw.MAX_ATTEMPTS):
            with self.assertRaises(pw.ResetError):
                pw.confirm_reset('talaba@test.uz', wrong, 'YangiParol12345')

        # Endi TO'G'RI kod ham ishlamaydi
        with self.assertRaises(pw.ResetError) as ctx:
            pw.confirm_reset('talaba@test.uz', code, 'YangiParol12345')
        self.assertIn("Juda ko'p", ctx.exception.message)

    def test_muddati_otgan_kod_ishlamaydi(self):
        from datetime import timedelta
        from django.utils import timezone as tz
        from core import password_reset as pw
        from core.models import PasswordReset

        pw.request_reset('talaba@test.uz')
        code = self._get_code()
        PasswordReset.objects.update(expires_at=tz.now() - timedelta(minutes=1))

        with self.assertRaises(pw.ResetError):
            pw.confirm_reset('talaba@test.uz', code, 'YangiParol12345')

    def test_bosh_parol_amaldagi_kodni_sarflamaydi(self):
        """Parol tekshiruvi kod tekshiruvidan OLDIN bo'lishi kerak."""
        from core import password_reset as pw
        from core.models import PasswordReset

        pw.request_reset('talaba@test.uz')
        code = self._get_code()

        with self.assertRaises(pw.ResetError):
            pw.confirm_reset('talaba@test.uz', code, '123')  # juda qisqa

        self.assertEqual(PasswordReset.objects.get().attempts, 0)
        # Kod hali ham ishlaydi
        pw.confirm_reset('talaba@test.uz', code, 'YangiParol12345')

    def test_zaif_parol_qabul_qilinmaydi(self):
        from core import password_reset as pw
        pw.request_reset('talaba@test.uz')
        code = self._get_code()
        for weak in ('123', '12345678', 'password'):
            with self.subTest(parol=weak):
                with self.assertRaises(pw.ResetError):
                    pw.confirm_reset('talaba@test.uz', code, weak)

    # ── Sahifalar ──

    def test_sahifalar_ochiladi(self):
        for name in ('forgot_password', 'reset_password'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_toliq_oqim_sahifalar_orqali(self):
        self.client.post(reverse('forgot_password'), {'email': 'talaba@test.uz'})
        code = self._get_code()

        response = self.client.post(reverse('reset_password'), {
            'email': 'talaba@test.uz', 'code': code,
            'password': 'YangiParol12345', 'password2': 'YangiParol12345',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

        self.assertTrue(self.client.login(username='talaba', password='YangiParol12345'))

    def test_mos_kelmagan_parollar(self):
        self.client.post(reverse('forgot_password'), {'email': 'talaba@test.uz'})
        response = self.client.post(reverse('reset_password'), {
            'email': 'talaba@test.uz', 'code': self._get_code(),
            'password': 'YangiParol12345', 'password2': 'BoshqaParol9999',
        })
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('EskiParol12345'))


class RegistrationEmailTests(TestCase):
    """Email endi majburiy — parol tiklash faqat shu orqali ishlaydi."""

    def test_emailsiz_royxatdan_otib_bolmaydi(self):
        response = self.client.post(reverse('register'), {
            'username': 'yangi',
            'email': '',
            'password': 'JudaKuchliParol9',
            'password2': 'JudaKuchliParol9',
            'full_name': 'Yangi',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='yangi').exists())

    def test_email_bilan_royxatdan_otadi(self):
        response = self.client.post(reverse('register'), {
            'username': 'yangi',
            'email': 'yangi@test.uz',
            'password': 'JudaKuchliParol9',
            'password2': 'JudaKuchliParol9',
            'full_name': 'Yangi',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.get(username='yangi').email, 'yangi@test.uz')
