import json
"""
3-bosqich testlari: login cheklovi, sertifikatlar, kod muharriri tili.

Ishga tushirish:  python manage.py test core.tests_phase3
"""

from datetime import timedelta

from django.contrib.auth.models import User
from core.test_utils import approve_all
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing.services import extend_subscription
from billing.models import PaymentMethod, PeriodSource

from . import certificates, lockout
from .models import (
    Category,
    Certificate,
    Challenge,
    Choice,
    Lesson,
    LoginAttempt,
    Module,
    Question,
    Quiz,
    QuizResult,
)


# ==========================================================================
# Login cheklovi
# ==========================================================================


class LockoutTests(TestCase):
    """Brute-force himoyasi."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='talaba', email='t@test.uz', password='TogriParol12345'
        )
        # O'quvchi logini endi API da. Qulf MODULI ikkalasida bir xil
        # (`core.lockout`) — nusxa yozilmagan.
        self.url = reverse('api:login')
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def _try(self, password='NotogriParol', username='talaba'):
        return self.client.post(
            self.url,
            data=json.dumps({'username': username, 'password': password}),
            content_type='application/json',
        )

    def test_notogri_urinish_yoziladi(self):
        self._try()
        attempt = LoginAttempt.objects.get()
        self.assertFalse(attempt.successful)
        self.assertEqual(attempt.username, 'talaba')
        self.assertEqual(attempt.purpose, LoginAttempt.Purpose.LOGIN)

    def test_besh_urinishdan_keyin_qulflanadi(self):
        for _ in range(lockout.MAX_PER_USERNAME):
            self._try()

        # Endi TO'G'RI parol ham o'tmaydi
        response = self._try(password='TogriParol12345')
        self.assertEqual(response.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_qulf_davomida_yangi_urinish_yozilmaydi(self):
        """
        Aks holda hujumchi urinib turib qulfni cheksiz uzaytirardi va
        haqiqiy egasi hech qachon kira olmasdi.
        """
        for _ in range(lockout.MAX_PER_USERNAME):
            self._try()
        count_after_lock = LoginAttempt.objects.count()

        for _ in range(3):
            self._try()

        self.assertEqual(LoginAttempt.objects.count(), count_after_lock)

    def test_qulf_muddati_otgach_ochiladi(self):
        for _ in range(lockout.MAX_PER_USERNAME):
            self._try()
        self.assertEqual(self._try(password='TogriParol12345').status_code, 429)

        # Urinishlarni o'tmishga suramiz
        LoginAttempt.objects.update(
            created_at=timezone.now() - lockout.COOLDOWN - timedelta(minutes=1)
        )

        response = self._try(password='TogriParol12345')
        self.assertEqual(response.status_code, 200)
        self.assertIn('_auth_user_id', self.client.session)

    def test_muvaffaqiyatli_kirish_hisoblagichni_tozalaydi(self):
        for _ in range(3):
            self._try()
        self._try(password='TogriParol12345')

        self.assertEqual(
            LoginAttempt.objects.filter(username='talaba', successful=False).count(), 0
        )
        self.assertEqual(
            LoginAttempt.objects.filter(username='talaba', successful=True).count(), 1
        )

    def test_mavjud_bolmagan_nom_ham_qulflanadi(self):
        """ANTI-ENUMERATSIYA: javob foydalanuvchi borligini oshkor qilmasin."""
        for _ in range(lockout.MAX_PER_USERNAME):
            self._try(username='umuman_yoq')
        response = self._try(username='umuman_yoq')
        self.assertEqual(response.status_code, 429)

    def test_ip_boyicha_ham_cheklanadi(self):
        """Turli nomlarni sinash (parol purkash) ham bloklanishi kerak."""
        for i in range(lockout.MAX_PER_IP):
            self._try(username=f'user{i}')

        # Yangi, hali urinilmagan nom ham bloklanadi — IP cheklovi ishladi
        response = self._try(username='butunlay_yangi')
        self.assertEqual(response.status_code, 429)

    def test_muvaffaqiyat_ip_hisoblagichini_tozalamaydi(self):
        """
        Hujumchi o'z hisobiga kirib IP cheklovini nolga tushira olmasligi kerak.
        """
        for i in range(3):
            self._try(username=f'user{i}')
        self._try(password='TogriParol12345')

        self.assertEqual(
            LoginAttempt.objects.filter(successful=False).exclude(username='talaba').count(),
            3,
        )

    def test_client_ip_xforwarded_oxirgisini_oladi(self):
        """
        nginx O'ZI ko'rgan manzilni ro'yxat OXIRIGA qo'shadi. Chapdagilar
        klientdan kelgan va soxta bo'lishi mumkin.
        """
        class FakeRequest:
            META = {
                'HTTP_X_FORWARDED_FOR': '1.2.3.4, 5.6.7.8, 203.0.113.9',
                'REMOTE_ADDR': '127.0.0.1',
            }

        self.assertEqual(lockout.client_ip(FakeRequest()), '203.0.113.9')

    def test_xforwarded_yoq_bolsa_remote_addr(self):
        class FakeRequest:
            META = {'REMOTE_ADDR': '198.51.100.7'}

        self.assertEqual(lockout.client_ip(FakeRequest()), '198.51.100.7')

    def test_eski_yozuvlar_ochiriladi(self):
        self._try()
        LoginAttempt.objects.update(
            created_at=timezone.now() - lockout.RETENTION - timedelta(days=1)
        )
        self.assertEqual(lockout.prune_old(), 1)
        self.assertEqual(LoginAttempt.objects.count(), 0)


class ResetThrottleTests(TestCase):
    """Parol tiklash so'rovi email spam vositasi bo'lmasligi kerak."""

    def setUp(self):
        User.objects.create_user(username='talaba', email='t@test.uz', password='Parol12345678')
        # Sahifa React'da; bu yerda API endpointi sinaladi
        self.url = reverse('api:password_reset')
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def test_kop_sorov_cheklanadi(self):
        for _ in range(lockout.MAX_RESET_PER_IP):
            self.client.post(self.url, {'email': 't@test.uz'})

        response = self.client.post(self.url, {'email': 't@test.uz'})
        self.assertEqual(response.status_code, 429)

    def test_tiklash_login_hisoblagichiga_tegmaydi(self):
        """
        Ikki cheklov ARALASHMASLIGI kerak: tiklash so'rovi foydalanuvchini
        kirishdan mahrum qilmasin.
        """
        for _ in range(lockout.MAX_RESET_PER_IP):
            self.client.post(self.url, {'email': 't@test.uz'})

        locked, _, _ = lockout.check_locked('talaba', '127.0.0.1')
        self.assertFalse(locked)

        # O'quvchi logini endi API da. Muvaffaqiyatli kirish 200
        # qaytaradi (yo'naltirish emas) — frontend o'zi navigatsiya
        # qiladi.
        response = self.client.post(
            reverse('api:login'),
            data=json.dumps({'username': 'talaba', 'password': 'Parol12345678'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)


# ==========================================================================
# Sertifikatlar
# ==========================================================================


class CertificateTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Python", slug="python")
        self.module = Module.objects.create(category=self.category, title="Asoslar", order=1)
        self.lesson = Lesson.objects.create(
            module=self.module, title="Kirish", order=1, is_free=True
        )
        self.quiz = Quiz.objects.create(lesson=self.lesson, title="Yakuniy imtihon")

        self.q1 = Question.objects.create(quiz=self.quiz, text="2+2?")
        self.q1_ok = Choice.objects.create(question=self.q1, text="4", is_correct=True)
        self.q1_bad = Choice.objects.create(question=self.q1, text="5", is_correct=False)

        self.user = User.objects.create_user(
            username='talaba', email='t@test.uz', password='Parol12345678'
        )
        self.user.profile.full_name = "Ozodbek O'turayev"
        self.user.profile.save()
        self.client.force_login(self.user)
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def _result(self, score):
        return QuizResult.objects.create(
            user=self.user, quiz=self.quiz, score_percentage=score,
            correct_count=1, total_questions=1,
        )

    def test_80_dan_past_sertifikat_bermaydi(self):
        for score in (0, 50, 79):
            with self.subTest(score=score):
                QuizResult.objects.all().delete()
                self.assertIsNone(certificates.issue_for_result(self._result(score)))

    def test_80_va_undan_yuqori_sertifikat_beradi(self):
        cert = certificates.issue_for_result(self._result(80))
        self.assertIsNotNone(cert)
        self.assertEqual(cert.score_percentage, 80)
        self.assertEqual(cert.full_name, "Ozodbek O'turayev")
        self.assertEqual(cert.quiz_title, "Yakuniy imtihon")
        self.assertEqual(cert.category_name, "Python")

    def test_idempotent(self):
        result = self._result(90)
        first = certificates.issue_for_result(result)
        second = certificates.issue_for_result(result)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Certificate.objects.count(), 1)

    def test_ball_muzlatiladi(self):
        """Test qayta topshirilsa ham berilgan hujjat qayta yozilmaydi."""
        result = self._result(85)
        cert = certificates.issue_for_result(result)

        result.score_percentage = 100
        result.save()
        certificates.issue_for_result(result)

        cert.refresh_from_db()
        self.assertEqual(cert.score_percentage, 85)

    def test_kod_ketma_ket_emas(self):
        """/verify/1, /verify/2 deb sanab chiqib bo'lmasligi kerak."""
        codes = {certificates.generate_code() for _ in range(50)}
        self.assertEqual(len(codes), 50)
        self.assertTrue(all(len(c) == certificates.CODE_BYTES * 2 for c in codes))

    def test_testni_topshirish_sertifikat_beradi(self):
        import json
        response = self.client.post(
            reverse('api:quiz_submit', args=[self.quiz.id]),
            data=json.dumps({'answers': {str(self.q1.id): self.q1_ok.id}}),
            content_type='application/json',
        )
        data = response.json()
        self.assertEqual(data['score'], 100)
        self.assertIsNotNone(data['certificate'], 'Sertifikat berilishi kerak')
        self.assertTrue(data['certificate']['pdf_url'])
        self.assertEqual(Certificate.objects.filter(user=self.user).count(), 1)

    def test_past_ball_sertifikat_havolasini_bermaydi(self):
        import json
        data = self.client.post(
            reverse('api:quiz_submit', args=[self.quiz.id]),
            data=json.dumps({'answers': {str(self.q1.id): self.q1_bad.id}}),
            content_type='application/json',
        ).json()
        self.assertEqual(data['score'], 0)
        self.assertIsNone(data['certificate'], 'Past ballda sertifikat berilmaydi')

    # ── PDF ──

    def test_pdf_yaratiladi(self):
        cert = certificates.issue_for_result(self._result(95))
        pdf = certificates.build_pdf(cert, verify_url="https://example.uz/verify/")
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 1000)

    def test_pdf_yuklab_olish(self):
        cert = certificates.issue_for_result(self._result(95))
        response = self.client.get(reverse('certificate_pdf', args=[cert.code]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])

    def test_begona_sertifikatni_yuklab_bolmaydi(self):
        cert = certificates.issue_for_result(self._result(95))
        other = User.objects.create_user(username='boshqa', password='Parol12345678')
        approve_all()   # setUp dan KEYIN yaratildi — ruxsatni qayta ochamiz
        self.client.force_login(other)
        self.assertEqual(
            self.client.get(reverse('certificate_pdf', args=[cert.code])).status_code, 404
        )

    # ── Tekshirish sahifasi ──

    def test_tekshirish_login_talab_qilmaydi(self):
        cert = certificates.issue_for_result(self._result(95))
        self.client.logout()
        response = self.client.get(reverse('api:verify_certificate'), {'code': cert.code})
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data['found'])
        self.assertTrue(data['valid'])
        self.assertIn('Ozodbek', data['holder'])

    def test_tekshirish_shaxsiy_malumot_chiqarmaydi(self):
        cert = certificates.issue_for_result(self._result(95))
        self.client.logout()
        response = self.client.get(reverse('api:verify_certificate'), {'code': cert.code})

        # Ish beruvchiga faqat sertifikat ma'lumoti kerak — email va
        # login unga tegishli emas.
        raw = json.dumps(response.json(), ensure_ascii=False)
        self.assertNotIn('t@test.uz', raw)
        self.assertNotIn('talaba', raw)

    def test_notogri_kod(self):
        self.client.logout()
        response = self.client.get(reverse('api:verify_certificate'), {'code': 'YOQBUNDAYKOD'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['found'])

    def test_bekor_qilingan_sertifikat(self):
        cert = certificates.issue_for_result(self._result(95))
        cert.revoked_at = timezone.now()
        cert.revoke_reason = "Aldash aniqlandi"
        cert.save()

        self.client.logout()
        data = self.client.get(
            reverse('api:verify_certificate'), {'code': cert.code}
        ).json()

        self.assertTrue(data['found'], "Sertifikat topilishi kerak — u mavjud")
        self.assertFalse(data['valid'], 'Bekor qilingan sertifikat haqiqiy emas')
        self.assertEqual(data['revoke_reason'], 'Aldash aniqlandi')

    def test_dashboard_haqiqiy_sertifikatlarni_sanaydi(self):
        certificates.issue_for_result(self._result(95))
        self.assertEqual(self.client.get(reverse('api:dashboard')).json()['certificates'], 1)

        # Bekor qilingan sertifikat sanalmaydi
        Certificate.objects.update(revoked_at=timezone.now())
        self.assertEqual(self.client.get(reverse('api:dashboard')).json()['certificates'], 0)

    def test_sertifikatlar_sahifasi(self):
        certificates.issue_for_result(self._result(95))
        response = self.client.get(reverse('api:certificates'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)


# ==========================================================================
# Kod muharriri
# ==========================================================================


@override_settings(TELEGRAM_BOT_TOKEN='', TELEGRAM_ADMIN_CHAT_IDS=[])
class TelegramMockTests(TestCase):
    """
    Token sozlanmaganda hech qayerga so'rov ketmasligi va HECH QACHON
    xato tashlanmasligi kerak — xabarnoma to'lov oqimini yiqitmasin.

    SOZLAMA ATAYLAB MAJBURLANADI. Ilgari test `.env` dan o'qirdi va
    "token bo'sh" degan taxminga tayanardi. Dasturchi tokenni
    to'ldirgan kuni test yiqilardi — kodda hech narsa buzilmagan
    bo'lsa ham. Test o'z shartini o'zi qo'yishi kerak.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='talaba', email='t@test.uz', password='Parol12345678'
        )
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def test_sozlanmagan_holda_xato_bermaydi(self):
        from billing import telegram
        self.assertFalse(telegram.is_configured())
        # Hech biri xato tashlamasligi kerak
        telegram.send_to_admins("sinov")
        telegram.notify_confirmed(self.user, 3, 30_000_000, timezone.now())
        telegram.notify_rejected(self.user, "sabab")
        telegram.notify_expiring(self.user, 3, timezone.now(), 3)

    def test_chat_id_yoq_bolsa_yubormaydi(self):
        from billing import telegram
        self.assertIsNone(telegram.user_chat_id(self.user))
        self.assertFalse(telegram.send(None, "matn"))

    def test_ulash_kodi_xeshlangan(self):
        from billing import telegram
        from billing.models import TelegramLinkToken

        url = telegram.create_link_token(self.user)
        token = url.split('start=')[1]

        record = TelegramLinkToken.objects.get(user=self.user)
        self.assertNotEqual(record.token_hash, token)
        self.assertEqual(len(record.token_hash), 64)

    def test_kod_bir_marta_ishlaydi(self):
        from billing import telegram

        url = telegram.create_link_token(self.user)
        token = url.split('start=')[1]

        self.assertEqual(telegram.consume_link_token(token, 12345), self.user)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.telegram_chat_id, '12345')

        self.assertIsNone(telegram.consume_link_token(token, 99999))

    def test_yangi_kod_eskisini_bekor_qiladi(self):
        from billing import telegram

        old_token = telegram.create_link_token(self.user).split('start=')[1]
        telegram.create_link_token(self.user)

        self.assertIsNone(telegram.consume_link_token(old_token, 12345))

    def test_webhook_notogri_maxfiy_soz_404(self):
        response = self.client.post(
            reverse('billing:telegram_webhook', args=['notogri']),
            data='{}', content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
