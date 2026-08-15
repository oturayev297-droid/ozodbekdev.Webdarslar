"""
API testlari
============

ASOSIY XAVF: API paywallda TESHIK ochib qo'yishi. Shablonli sahifa
himoyalangan bo'lsa-yu, o'sha mazmun `/api/v1/` orqali ochiq chiqsa —
obunaning ma'nosi qolmaydi va buni hech kim sezmaydi, chunki sayt
tashqi ko'rinishidan xuddi shunday ishlab turadi.

Shuning uchun bu yerda uch narsa qattiq tekshiriladi:

  1. Qulflangan darsning MAZMUNI javobga umuman tushmasligi
  2. Test javoblari (`is_correct`) hech qachon yuborilmasligi
  3. Ruxsat va obuna darvozalari API da ham ishlashi
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from billing.models import PeriodSource, SubscriptionPlan
from billing.services import extend_subscription
from core.models import Category, Choice, Lesson, Module, Profile, Question, Quiz

SECRET_TEXT = "Bu maxfiy dars matni va u hech qachon chiqmasligi kerak"


def make_user(username, approved=True, subscribed=False, staff=False):
    user = User.objects.create_user(username, password='juda-maxfiy-parol-7', is_staff=staff)
    profile = user.profile
    profile.is_approved = approved
    profile.save(update_fields=['is_approved'])
    if subscribed:
        extend_subscription(user, days=30, source=PeriodSource.ADMIN_GRANT)
    return user


class ApiBase(TestCase):
    def setUp(self):
        SubscriptionPlan.objects.create(
            code='TEST', name='Test tarif', price_per_month_tiyin=10_000_000
        )
        self.category = Category.objects.create(
            name='Python', slug='python', description='Tavsif'
        )
        module = Module.objects.create(category=self.category, title='Modul', order=1)

        self.free = Lesson.objects.create(
            module=module, title='Bepul dars', theory='Ochiq matn', order=1, is_free=True
        )
        self.paid = Lesson.objects.create(
            module=module, title='Pullik dars', theory=SECRET_TEXT, order=2, is_free=False,
            practice_code='print("maxfiy kod")',
        )

        self.quiz = Quiz.objects.create(
            lesson=self.paid, title='Test', is_published=True
        )
        question = Question.objects.create(quiz=self.quiz, text='2+2?')
        self.correct = Choice.objects.create(question=question, text='4', is_correct=True)
        Choice.objects.create(question=question, text='5', is_correct=False)
        self.question = question


# ══════════════════════════ Paywall ══════════════════════════


class ContentLeakTests(ApiBase):
    """Qulflangan mazmun API orqali chiqmasligi."""

    def setUp(self):
        super().setUp()
        self.client.force_login(make_user('obunasiz'))

    def test_qulflangan_dars_402_qaytaradi(self):
        response = self.client.get(reverse('api:lesson_detail', args=[self.paid.id]))
        self.assertEqual(response.status_code, 402)

    def test_qulflangan_dars_MATNI_javobda_yoq(self):
        """Eng to'g'ridan-to'g'ri tekshiruv: butun JSON ichida qidiramiz."""
        response = self.client.get(reverse('api:lesson_detail', args=[self.paid.id]))
        raw = json.dumps(response.json(), ensure_ascii=False)
        self.assertNotIn(SECRET_TEXT, raw)

    def test_qulflangan_dars_KODI_javobda_yoq(self):
        response = self.client.get(reverse('api:lesson_detail', args=[self.paid.id]))
        raw = json.dumps(response.json(), ensure_ascii=False)
        self.assertNotIn('maxfiy kod', raw)

    def test_qulflangan_darsda_mazmun_MAYDONLARI_yoq(self):
        response = self.client.get(reverse('api:lesson_detail', args=[self.paid.id]))
        data = response.json()
        for field in ('theory_html', 'practice_code', 'images', 'video_url'):
            with self.subTest(field=field):
                self.assertNotIn(field, data)

    def test_qulflangan_darsning_SARLAVHASI_korinadi(self):
        """O'quvchi nima sotib olayotganini bilishi kerak."""
        response = self.client.get(reverse('api:lesson_detail', args=[self.paid.id]))
        self.assertEqual(response.json()['title'], 'Pullik dars')

    def test_bepul_dars_ochiq(self):
        response = self.client.get(reverse('api:lesson_detail', args=[self.free.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('theory_html', response.json())

    def test_royxatda_ham_matn_yoq(self):
        """Ro'yxat serializeri mazmun bermasligi kerak — hatto ochiq darsda ham."""
        response = self.client.get(reverse('api:course_detail', args=['python']))
        raw = json.dumps(response.json(), ensure_ascii=False)
        self.assertNotIn(SECRET_TEXT, raw)
        self.assertNotIn('Ochiq matn', raw)

    def test_obuna_bilan_ochiladi(self):
        self.client.force_login(make_user('obunali', subscribed=True))
        response = self.client.get(reverse('api:lesson_detail', args=[self.paid.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(SECRET_TEXT, response.json()['theory_html'])


class QuizAnswerLeakTests(ApiBase):
    """
    To'g'ri javoblar HECH QACHON klientga yuborilmasligi.

    Bu qoida buzilsa test ham, sertifikat ham ma'nosini yo'qotadi va
    buni sezish uchun hech qanday belgi bo'lmaydi.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(make_user('obunali2', subscribed=True))

    def test_is_correct_javobda_yoq(self):
        response = self.client.get(reverse('api:quiz_detail', args=[self.quiz.id]))
        raw = json.dumps(response.json(), ensure_ascii=False)
        self.assertNotIn('is_correct', raw)

    def test_variantlarda_faqat_id_va_matn(self):
        response = self.client.get(reverse('api:quiz_detail', args=[self.quiz.id]))
        choice = response.json()['questions'][0]['choices'][0]
        self.assertEqual(set(choice.keys()), {'id', 'text'})

    def test_ball_serverda_hisoblanadi(self):
        response = self.client.post(
            reverse('api:quiz_submit', args=[self.quiz.id]),
            data=json.dumps({'answers': {str(self.question.id): self.correct.id}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['score'], 100)

    def test_klientdan_kelgan_ball_etiborsiz_qoldiriladi(self):
        """Soxta "score" yuborilsa ham natija serverda hisoblanadi."""
        wrong = Choice.objects.get(question=self.question, is_correct=False)
        response = self.client.post(
            reverse('api:quiz_submit', args=[self.quiz.id]),
            data=json.dumps({
                'answers': {str(self.question.id): wrong.id},
                'score': 100,      # soxta — e'tiborsiz qoldirilishi kerak
                'correct': 999,    # soxta
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['score'], 0, "Ball faqat serverda hisoblanadi")
        self.assertEqual(response.json()['correct'], 0)

    def test_bosh_javoblar_rad_etiladi(self):
        """
        Bo'sh topshirish ATAYLAB xato beradi: tasodifiy bosilgan tugma
        o'quvchining natijasini nolga tushirib yubormasligi kerak.
        """
        response = self.client.post(
            reverse('api:quiz_submit', args=[self.quiz.id]),
            data=json.dumps({'answers': {}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_boshqa_testning_tanlovi_hisobga_olinmaydi(self):
        """
        To'g'ri variantlar FAQAT shu testdan olinadi. Butun bazadan
        olinsa, boshqa testning tanlov id si ham "to'g'ri" bo'lardi.
        """
        other_lesson = Lesson.objects.create(
            module=self.paid.module, title='Boshqa', theory='M', order=3, is_free=True
        )
        other_quiz = Quiz.objects.create(lesson=other_lesson, title='Boshqa test', is_published=True)
        other_q = Question.objects.create(quiz=other_quiz, text='Savol')
        other_correct = Choice.objects.create(question=other_q, text='Ha', is_correct=True)

        response = self.client.post(
            reverse('api:quiz_submit', args=[self.quiz.id]),
            data=json.dumps({'answers': {str(self.question.id): other_correct.id}}),
            content_type='application/json',
        )
        self.assertEqual(response.json()['score'], 0)

    def test_qoralama_test_korinmaydi(self):
        Quiz.objects.filter(pk=self.quiz.pk).update(is_published=False)
        response = self.client.get(reverse('api:quiz_detail', args=[self.quiz.id]))
        self.assertEqual(response.status_code, 404)


# ══════════════════════════ Darvozalar ══════════════════════════


class ApprovalGateTests(ApiBase):
    """Admin ruxsati API da ham talab qilinishi."""

    GUARDED = ['api:courses', 'api:quizzes', 'api:dashboard', 'api:certificates']

    def test_ruxsatsiz_403_oladi(self):
        self.client.force_login(make_user('ruxsatsiz', approved=False))
        for name in self.GUARDED:
            with self.subTest(endpoint=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_ruxsatsiz_dars_ololmaydi(self):
        self.client.force_login(make_user('ruxsatsiz2', approved=False))
        response = self.client.get(reverse('api:lesson_detail', args=[self.free.id]))
        self.assertEqual(response.status_code, 403)

    def test_ruxsatsiz_ham_OZ_HOLATINI_kora_oladi(self):
        """
        `/auth/me/` ruxsat talab qilmaydi — frontend aynan shu javob
        bilan "kutish" ekranini ko'rsatadi. Yopilsa, ruxsatsiz odam
        hech narsa ko'rmay qolardi.
        """
        self.client.force_login(make_user('ruxsatsiz3', approved=False))
        response = self.client.get(reverse('api:me'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['user']['is_approved'])

    def test_anonim_kira_olmaydi(self):
        for name in self.GUARDED:
            with self.subTest(endpoint=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_sertifikat_tekshirish_OCHIQ(self):
        """Ish beruvchining tizimda hisobi yo'q."""
        response = self.client.get(reverse('api:verify_certificate'), {'code': 'YOQ'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['found'])


# ══════════════════════════ Autentifikatsiya ══════════════════════════


class AuthTests(ApiBase):
    def test_login_va_me(self):
        make_user('kiruvchi')
        response = self.client.post(
            reverse('api:login'),
            data=json.dumps({'username': 'kiruvchi', 'password': 'juda-maxfiy-parol-7'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['username'], 'kiruvchi')

    def test_notogri_parol_401(self):
        make_user('kiruvchi2')
        response = self.client.post(
            reverse('api:login'),
            data=json.dumps({'username': 'kiruvchi2', 'password': 'notogri'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    def test_brute_force_himoyasi_API_da_ham_ishlaydi(self):
        """
        Cheklov shablonli login bilan BIR XIL modul orqali. Ikkinchi
        nusxa yozilsa, hujumchi API orqali cheklovsiz urinardi.
        """
        make_user('nishon')
        from core.lockout import MAX_PER_USERNAME

        for _ in range(MAX_PER_USERNAME):
            self.client.post(
                reverse('api:login'),
                data=json.dumps({'username': 'nishon', 'password': 'notogri'}),
                content_type='application/json',
            )

        response = self.client.post(
            reverse('api:login'),
            data=json.dumps({'username': 'nishon', 'password': 'juda-maxfiy-parol-7'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 429, "Qulf API da ham ishlashi kerak")

    def test_royxatdan_otgan_hisob_RUXSATSIZ_yaratiladi(self):
        response = self.client.post(
            reverse('api:register'),
            data=json.dumps({
                'username': 'yangiapi',
                'email': 'yangiapi@example.com',
                'password': 'juda-maxfiy-parol-7',
                'full_name': 'Yangi',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(
            Profile.objects.get(user__username='yangiapi').is_approved,
            "API orqali ochiq hisob yaratib bo'lmasligi kerak",
        )

    def test_band_login_rad_etiladi(self):
        make_user('bandnom')
        response = self.client.post(
            reverse('api:register'),
            data=json.dumps({
                'username': 'bandnom',
                'email': 'boshqa@example.com',
                'password': 'juda-maxfiy-parol-7',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_zaif_parol_rad_etiladi(self):
        response = self.client.post(
            reverse('api:register'),
            data=json.dumps({
                'username': 'zaifparol',
                'email': 'zaif@example.com',
                'password': '12345678',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.json())

    def test_csrf_token_beriladi(self):
        response = self.client.get(reverse('api:csrf'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['csrfToken'])


# ══════════════════════════ Obuna ══════════════════════════


class SubscriptionApiTests(ApiBase):
    def setUp(self):
        super().setUp()
        self.user = make_user('obunachi')
        self.client.force_login(self.user)

    def test_holat_va_tariflar(self):
        response = self.client.get(reverse('api:subscription'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['state']['active'])
        self.assertEqual([o['months'] for o in data['options']], [1])
        self.assertEqual(data['options'][0]['amount_display'], "100 000 so'm")

    def test_sorov_yaratiladi(self):
        response = self.client.post(
            reverse('api:payment_request'),
            data=json.dumps({'months': 1}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['amount_display'], "100 000 so'm")

    def test_ruxsat_etilmagan_muddat_rad_etiladi(self):
        response = self.client.post(
            reverse('api:payment_request'),
            data=json.dumps({'months': 3}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_summa_klientdan_OLINMAYDI(self):
        """Soxta summa yuborilsa ham server o'zi hisoblaydi."""
        self.client.post(
            reverse('api:payment_request'),
            data=json.dumps({'months': 1, 'amount_tiyin': 1}),
            content_type='application/json',
        )
        from billing.models import PaymentRequest

        self.assertEqual(PaymentRequest.objects.get().amount_tiyin, 10_000_000)


# ══════════════════════════ Kurslar ══════════════════════════


class CourseApiTests(ApiBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(make_user('talaba'))

    def test_kurslar_royxati(self):
        response = self.client.get(reverse('api:courses'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['total_lessons'], 2)
        self.assertEqual(data[0]['free_lessons'], 1)

    def test_bosh_bolim_royxatga_kirmaydi(self):
        """Darssiz bo'limni bosgan odam bo'sh ro'yxatga tushib qolardi."""
        Category.objects.create(name='Bo\'sh', slug='bosh')
        response = self.client.get(reverse('api:courses'))
        slugs = [c['slug'] for c in response.json()]
        self.assertNotIn('bosh', slugs)

    def test_bolim_tafsiloti(self):
        response = self.client.get(reverse('api:course_detail', args=['python']))
        self.assertEqual(response.status_code, 200)
        modules = response.json()['modules']
        self.assertEqual(len(modules), 1)
        self.assertEqual(len(modules[0]['lessons']), 2)

    def test_darsni_tugatish(self):
        response = self.client.post(reverse('api:lesson_complete', args=[self.free.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['completed_lessons'], 1)

    def test_qulflangan_darsni_tugatib_bolmaydi(self):
        response = self.client.post(reverse('api:lesson_complete', args=[self.paid.id]))
        self.assertEqual(response.status_code, 402)
