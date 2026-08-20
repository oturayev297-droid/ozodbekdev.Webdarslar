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
from core.models import (
    Category,
    Challenge,
    Choice,
    Lesson,
    Module,
    Profile,
    Question,
    Quiz,
)

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


# ══════════════════════════ Kod muharriri ══════════════════════════


class ChallengeApiTests(ApiBase):
    """
    Yechim ro'yxatga va topshiriq ma'lumotiga TUSHMASLIGI.

    Tushsa, u sahifa ochilishidayoq javobga kelib qolardi va
    topshiriqni yechishning ma'nosi qolmasdi.
    """

    SOLUTION = "print('bu yechim va u oldindan chiqmasligi kerak')"

    def setUp(self):
        super().setUp()
        self.challenge = Challenge.objects.create(
            title='Salom dunyo',
            language='python',
            description='Ekranga matn chiqaring',
            initial_code='# kodni yozing',
            solution_code=self.SOLUTION,
            order=1,
        )
        self.client.force_login(make_user('koder'))

    def test_royxatda_yechim_yoq(self):
        response = self.client.get(reverse('api:challenges'))
        raw = json.dumps(response.json(), ensure_ascii=False)
        self.assertNotIn(self.SOLUTION, raw)
        self.assertNotIn('solution', raw)

    def test_tafsilotda_ham_yechim_yoq(self):
        response = self.client.get(reverse('api:challenge_detail', args=[self.challenge.id]))
        raw = json.dumps(response.json(), ensure_ascii=False)
        self.assertNotIn(self.SOLUTION, raw)

    def test_yechim_borligi_aytiladi(self):
        """Yechimning O'ZI emas, BOR-YO'QLIGI — tugmani ko'rsatish uchun."""
        response = self.client.get(reverse('api:challenge_detail', args=[self.challenge.id]))
        self.assertTrue(response.json()['has_solution'])

    def test_yechim_ATAYLAB_soralganda_beriladi(self):
        response = self.client.get(
            reverse('api:challenge_solution', args=[self.challenge.id])
        )
        self.assertEqual(response.json()['solution'], self.SOLUTION)

    def test_til_boyicha_filtr(self):
        Challenge.objects.create(
            title='JS', language='javascript', description='d', order=2
        )
        response = self.client.get(reverse('api:challenges'), {'language': 'python'})
        languages = {row['language'] for row in response.json()}
        self.assertEqual(languages, {'python'})

    def test_ruxsatsiz_odam_topshiriq_ololmaydi(self):
        self.client.force_login(make_user('ruxsatsizkoder', approved=False))
        self.assertEqual(self.client.get(reverse('api:challenges')).status_code, 403)


# ══════════════════════════ Profil ══════════════════════════


class ProfileApiTests(ApiBase):
    def setUp(self):
        super().setUp()
        self.user = make_user('profilchi')
        self.client.force_login(self.user)

    def test_profilni_oqish(self):
        response = self.client.get(reverse('api:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['username'], 'profilchi')

    def test_profilni_tahrirlash(self):
        response = self.client.patch(
            reverse('api:profile'),
            data=json.dumps({'full_name': 'Yangi Ism'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, 'Yangi Ism')

    def test_ozini_ozi_TASDIQLAY_OLMAYDI(self):
        """
        `is_approved` serializerda yo'q. Bo'lganda o'quvchi bitta
        so'rov bilan admin ruxsatini o'ziga berib qo'yardi va butun
        darvoza ma'nosini yo'qotardi.

        Foydalanuvchi ATAYLAB ruxsatsiz yaratiladi — aks holda maydon
        o'zgardimi yoki yo'qmi bilib bo'lmasdi.
        """
        user = make_user('tasdiqsiz', approved=False)
        self.client.force_login(user)

        self.client.patch(
            reverse('api:profile'),
            data=json.dumps({'full_name': 'A', 'is_approved': True}),
            content_type='application/json',
        )

        user.profile.refresh_from_db()
        self.assertFalse(user.profile.is_approved)
        self.assertEqual(user.profile.full_name, 'A', "Ruxsat etilgan maydon o'zgarishi kerak")

    def test_darajani_ozgartirib_bolmaydi(self):
        """Level testlardan hisoblanadi — qo'lda qo'yib bo'lmaydi."""
        self.client.patch(
            reverse('api:profile'),
            data=json.dumps({'level': 99}),
            content_type='application/json',
        )
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.level, 1)

    def test_juda_katta_rasm_rad_etiladi(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        big = SimpleUploadedFile('katta.jpg', b'x' * (4 * 1024 * 1024), 'image/jpeg')
        response = self.client.post(reverse('api:profile_avatar'), {'image': big})
        self.assertEqual(response.status_code, 400)

    def test_notogri_format_rad_etiladi(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        bad = SimpleUploadedFile('virus.exe', b'MZ', 'application/octet-stream')
        response = self.client.post(reverse('api:profile_avatar'), {'image': bad})
        self.assertEqual(response.status_code, 400)

    def test_anonim_profil_kora_olmaydi(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('api:profile')).status_code, 403)


class MentorHistoryTests(ApiBase):
    """Tarix FAQAT o'ziniki bo'lishi."""

    def setUp(self):
        super().setUp()
        self.user = make_user('savolchi')
        self.other = make_user('boshqaodam')

        from core.models import MentorMessage

        MentorMessage.objects.create(
            user=self.user, question='Mening savolim', answer='Javob'
        )
        MentorMessage.objects.create(
            user=self.other, question='BEGONA SAVOL', answer='Javob'
        )
        self.client.force_login(self.user)

    def test_faqat_ozining_tarixi(self):
        response = self.client.get(reverse('api:mentor_history'))
        raw = json.dumps(response.json(), ensure_ascii=False)
        self.assertIn('Mening savolim', raw)
        self.assertNotIn('BEGONA SAVOL', raw)


class PaymentCardTests(ApiBase):
    """
    Karta rekvizitlari o'quvchiga YETIB BORISHI.

    NEGA ALOHIDA TEST: bu manzil hech qachon sinalmagan edi va u
    model obyektini to'g'ridan-to'g'ri javobga qo'yardi. Natijada
    admin kartani beradi, sahifa esa 500 oladi va uni jimgina yutib
    yuboradi (`.catch(() => setCard(null))`) — o'quvchi uchun karta
    shunchaki KELMAYDI, xato ham ko'rinmaydi.

    Shuning uchun bu yerda `status_code` emas, JAVOB MAZMUNI
    tekshiriladi: karta raqami javobda bormi.
    """

    CARD = {'number': '8600 1234 5678 9012', 'holder': 'OZODBEK T.', 'bank': 'Uzcard'}

    def setUp(self):
        super().setUp()
        from billing import payment_requests, services

        self.user = make_user('tolovchi')
        self.admin = make_user('kartachi', staff=True)
        services.update_cards([self.CARD])

        self.request = payment_requests.create_request(self.user, 1)
        self.client.force_login(self.user)

    def _issue(self):
        from billing import payment_requests

        payment_requests.issue_card(self.request.pk, self.admin)

    def test_karta_berilgach_oquvchiga_korinadi(self):
        self._issue()

        response = self.client.get(reverse('api:payment_card'))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([c['number'] for c in data['cards']], [self.CARD['number']])

    def test_javob_sorov_malumotini_ham_beradi(self):
        self._issue()

        data = self.client.get(reverse('api:payment_card')).json()

        self.assertEqual(data['request']['id'], self.request.pk)
        self.assertEqual(data['request']['status'], 'CARD_ISSUED')
        self.assertEqual(data['request']['months'], 1)

    def test_karta_berilmagan_bolsa_403(self):
        """
        Bu XATO EMAS, HOLAT: o'quvchi navbatda turibdi. 500 qaytsa
        sahifa "server buzilgan" degan taassurot qoldirardi.
        """
        response = self.client.get(reverse('api:payment_card'))

        self.assertEqual(response.status_code, 403)
        self.assertIn('detail', response.json())

    def test_begona_odam_kartani_ololmaydi(self):
        self._issue()
        self.client.force_login(make_user('chetdagi'))

        self.assertEqual(self.client.get(reverse('api:payment_card')).status_code, 403)

    def test_anonim_kartani_ololmaydi(self):
        self._issue()
        self.client.logout()

        self.assertEqual(self.client.get(reverse('api:payment_card')).status_code, 403)


class ChallengeCheckTests(ApiBase):
    """
    Muharrir topshirig'ini tekshirish.

    ENG MUHIM SHART — KUTILGAN NATIJA JAVOBGA TUSHMASLIGI. Tushsa,
    topshiriqni yechmasdan ko'chirib qo'yish mumkin bo'lardi: xuddi
    test javoblari kabi (`ChoiceSerializer` ga qarang).
    """

    def setUp(self):
        super().setUp()
        self.challenge = Challenge.objects.create(
            title='Salom', language='python', difficulty='Oson',
            description='Salom deb chiqaring',
            initial_code='', solution_code='print("Salom")',
            expected_output='Salom\n', order=1,
        )
        self.user = make_user('kodchi')
        self.client.force_login(self.user)

    def _check(self, output):
        return self.client.post(
            reverse('api:challenge_check', args=[self.challenge.id]),
            data=json.dumps({'output': output}),
            content_type='application/json',
        )

    def test_togri_natija_qabul_qilinadi(self):
        response = self._check('Salom\n')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['correct'])

    def test_notogri_natija_rad_etiladi(self):
        data = self._check('Xayr').json()

        self.assertFalse(data['correct'])
        self.assertEqual(data['diff']['line'], 1)

    def test_kutilgan_natija_javobga_TUSHMAYDI(self):
        """
        Faqat FARQ QILGAN qator ko'rsatiladi. Bu xatoni topishga
        yetadi, lekin ko'p qatorli javobni ochib bermaydi.
        """
        self.challenge.expected_output = 'birinchi\nikkinchi\nuchinchi\n'
        self.challenge.save(update_fields=['expected_output'])

        raw = json.dumps(self._check('birinchi\nXATO\nuchinchi').json(), ensure_ascii=False)

        self.assertIn('ikkinchi', raw)      # farq qilgan qator — ko'rinadi
        self.assertNotIn('uchinchi', raw)   # qolgan javob — ko'rinmaydi

    def test_topshiriq_royxatida_kutilgan_natija_yoq(self):
        raw = json.dumps(self.client.get(reverse('api:challenges')).json(), ensure_ascii=False)
        self.assertNotIn('Salom\n', raw)

        detail = self.client.get(
            reverse('api:challenge_detail', args=[self.challenge.id])
        ).json()
        self.assertNotIn('expected_output', detail)
        self.assertTrue(detail['has_check'])

    def test_yechilgan_topshiriq_royxatda_belgilanadi(self):
        self.assertFalse(self.client.get(reverse('api:challenges')).json()[0]['solved'])

        self._check('Salom')

        self.assertTrue(self.client.get(reverse('api:challenges')).json()[0]['solved'])

    def test_urinishlar_sanaladi(self):
        self._check('xato')
        self.assertEqual(self._check('yana xato').json()['attempts'], 2)

    def test_birinchi_yechim_sanasi_saqlanadi(self):
        first = self._check('Salom').json()['solved_at']
        again = self._check('Salom').json()['solved_at']

        # Ikkinchi tekshiruv sanani YANGILAMAYDI: "qachon yechgan edim"
        # degan ma'lumot har tugma bosilganda o'chib ketmasligi kerak.
        self.assertEqual(first, again)

    def test_tekshiruvsiz_topshiriq_400(self):
        self.challenge.expected_output = ''
        self.challenge.save(update_fields=['expected_output'])

        self.assertEqual(self._check('nima bolsa ham').status_code, 400)

    def test_matn_bolmagan_natija_rad_etiladi(self):
        response = self.client.post(
            reverse('api:challenge_check', args=[self.challenge.id]),
            data=json.dumps({'output': {'hiyla': True}}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_anonim_tekshira_olmaydi(self):
        self.client.logout()
        self.assertEqual(self._check('Salom').status_code, 403)

    def test_bosh_natija_uchun_alohida_maslahat(self):
        self.assertIn('chiqar', self._check('').json()['detail'].lower())
