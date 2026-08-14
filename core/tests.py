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
    """Kichik, lekin to'liq kontent daraxti."""

    def build_content(self):
        self.category = Category.objects.create(name="Python", slug="python")
        self.module = Module.objects.create(category=self.category, title="Asoslar", order=1)
        self.lesson = Lesson.objects.create(
            module=self.module, title="Kirish", theory="Nazariya", order=1
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
        other_lesson = Lesson.objects.create(module=self.module, title="Boshqa", order=2)
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
