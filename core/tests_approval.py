"""
Admin ruxsati darvozasi testlari.

ENG MUHIM QOIDA: ruxsat va obuna — IKKI ALOHIDA darvoza va ikkalasi
ham o'tishi kerak. Chalkashtirilsa:

  * ruxsat obunani almashtirsa — bir marta to'lagan odam abadiy kirardi
  * obuna ruxsatni almashtirsa — admin kimni qabul qilishini nazorat
    qila olmasdi

Shuning uchun har ikkalasi alohida ham, birga ham tekshiriladi.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from billing.models import PeriodSource, SubscriptionPlan
from billing.services import extend_subscription
from core.approval import approve, is_approved, revoke
from core.models import Category, Lesson, Module, Profile


def make_student(username, approved=False, subscribed=False):
    """
    Sinov o'quvchisi.

    DIQQAT — `user.profile` ISHLATILADI, `Profile.objects.get_or_create`
    EMAS. Profil `create_user` dagi signal bilan yaratiladi va o'sha
    payt `user` obyektiga KESHLANADI. `get_or_create` esa bazadan
    YANGI Python obyekt qaytaradi: uni o'zgartirsak, keyin `user.profile`
    baribir eski keshdagi nusxani berardi va test yolg'on yiqilardi.
    """
    user = User.objects.create_user(username, password='juda-maxfiy-parol-9')
    profile = user.profile
    profile.is_approved = approved
    profile.save(update_fields=['is_approved'])
    if subscribed:
        extend_subscription(user, days=30, source=PeriodSource.ADMIN_GRANT)
    return user


class ApprovalGateTests(TestCase):
    """Ruxsatsiz o'quvchi kontentni ko'rmasligi."""

    #: Ruxsat talab qiladigan sahifalar
    GUARDED = ['lessons', 'dashboard', 'projects', 'quizzes', 'editor', 'my_certificates']

    def setUp(self):
        Category.objects.create(name='Python', slug='python')

    def test_ruxsatsiz_oquvchi_kutish_sahifasiga_yuboriladi(self):
        self.client.force_login(make_student('kutuvchi'))

        for name in self.GUARDED:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertRedirects(response, reverse('pending_approval'))

    def test_ruxsatli_oquvchi_otadi(self):
        self.client.force_login(make_student('ruxsatli', approved=True))

        for name in self.GUARDED:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_xodim_ruxsatsiz_ham_otadi(self):
        """Admin o'ziga ruxsat berib o'tirmasin."""
        staff = User.objects.create_user('xodim', password='juda-maxfiy-parol-9', is_staff=True)
        Profile.objects.filter(user=staff).update(is_approved=False)
        self.client.force_login(staff)

        self.assertEqual(self.client.get(reverse('lessons')).status_code, 200)

    def test_anonim_LOGIN_sahifasiga_yuboriladi_kutish_sahifasiga_EMAS(self):
        """
        Kirmagan odam va kirgan-u ruxsatsiz odam — ikki xil holat.
        Ikkalasi bir joyga yuborilsa, anonim odam "ruxsat kutilmoqda"
        degan xabarni ko'rib butunlay chalkashardi.
        """
        response = self.client.get(reverse('lessons'))
        self.assertIn('/login/', response['Location'])

    def test_ruxsat_berilgach_darhol_ochiladi(self):
        student = make_student('yangi')
        self.client.force_login(student)
        self.assertRedirects(self.client.get(reverse('lessons')), reverse('pending_approval'))

        approve(student.profile)

        self.assertEqual(self.client.get(reverse('lessons')).status_code, 200)

    def test_ruxsat_olinsa_darhol_yopiladi(self):
        student = make_student('eski', approved=True)
        self.client.force_login(student)
        self.assertEqual(self.client.get(reverse('lessons')).status_code, 200)

        revoke(student.profile, reason='To\'lov kelmadi')

        self.assertRedirects(self.client.get(reverse('lessons')), reverse('pending_approval'))


class PendingPageTests(TestCase):
    def test_ruxsatli_odam_kutish_sahifasidan_qaytariladi(self):
        """
        Aks holda ruxsat berilgandan keyin ham eski havola bo'yicha
        kutish sahifasini ko'rib, hech narsa o'zgarmagandek tuyulardi.
        """
        self.client.force_login(make_student('ruxsatli2', approved=True))
        response = self.client.get(reverse('pending_approval'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_rad_etilgan_sabab_korsatiladi(self):
        student = make_student('radetilgan')
        revoke(student.profile, reason='Hujjatlar yetarli emas')
        self.client.force_login(student)

        response = self.client.get(reverse('pending_approval'))
        self.assertContains(response, 'Hujjatlar yetarli emas')

    def test_kutish_sahifasi_ochiladi(self):
        self.client.force_login(make_student('kutuvchi2'))
        response = self.client.get(reverse('pending_approval'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ruxsat kutilmoqda')


class RegistrationTests(TestCase):
    """Yangi hisob YOPIQ tug'ilishi."""

    DATA = {
        'username': 'yangiodam',
        'email': 'yangi@example.com',
        'password': 'juda-maxfiy-parol-9',
        'password2': 'juda-maxfiy-parol-9',
        'full_name': 'Yangi Odam',
    }

    def test_yangi_hisob_ruxsatsiz_yaratiladi(self):
        self.client.post(reverse('register'), self.DATA)

        profile = Profile.objects.get(user__username='yangiodam')
        self.assertFalse(
            profile.is_approved,
            "Yangi hisob YOPIQ tug'ilishi kerak (fail closed)",
        )

    def test_royxatdan_keyin_kutish_sahifasiga_yuboriladi(self):
        response = self.client.post(reverse('register'), self.DATA)
        self.assertRedirects(response, reverse('pending_approval'))

    def test_royxatdan_otgan_odam_darslarni_kormaydi(self):
        self.client.post(reverse('register'), self.DATA)
        self.assertRedirects(self.client.get(reverse('lessons')), reverse('pending_approval'))


class ApprovalAndSubscriptionTests(TestCase):
    """
    Ikkita darvoza BIRGA ishlashi.

    To'rt holat tekshiriladi — ikkalasidan biri yetishmasa kontent
    ochilmasligi kerak.
    """

    def setUp(self):
        SubscriptionPlan.objects.create(
            code='TEST', name='Test', price_per_month_tiyin=10_000_000
        )
        category = Category.objects.create(name='Python', slug='python')
        module = Module.objects.create(category=category, title='M', order=1)
        self.paid_lesson = Lesson.objects.create(
            module=module, title='Pullik', theory='Matn', order=1, is_free=False
        )

    def _can_see_paid_lesson(self, user):
        from billing.gating import can_access_lesson

        return can_access_lesson(user, self.paid_lesson)

    def test_ruxsatsiz_obunasiz__yopiq(self):
        user = make_student('a1')
        self.assertFalse(is_approved(user))
        self.assertFalse(self._can_see_paid_lesson(user))

    def test_ruxsatli_obunasiz__pullik_dars_yopiq(self):
        user = make_student('a2', approved=True)
        self.assertTrue(is_approved(user))
        self.assertFalse(
            self._can_see_paid_lesson(user),
            "Ruxsat obunaning o'rnini bosmasligi kerak",
        )

    def test_ruxsatsiz_obunali__sahifa_yopiq(self):
        """
        Obuna bor, lekin ruxsat yo'q — kontent sahifasiga umuman
        kira olmaydi. Obuna ruxsatning o'rnini bosmaydi.
        """
        user = make_student('a3', subscribed=True)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(reverse('lessons')), reverse('pending_approval'))

    def test_ruxsatli_obunali__ochiq(self):
        user = make_student('a4', approved=True, subscribed=True)
        self.assertTrue(self._can_see_paid_lesson(user))

        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('lessons')).status_code, 200)


class PanelApprovalTests(TestCase):
    """Paneldagi ruxsat tugmalari."""

    def setUp(self):
        self.staff = User.objects.create_user(
            'admin9', password='juda-maxfiy-parol-9', is_staff=True
        )
        self.client.force_login(self.staff)
        self.student = make_student('talaba')

    def test_ruxsat_beriladi(self):
        self.client.post(
            reverse('panel:student_approval', args=[self.student.id]), {'action': 'approve'}
        )
        self.student.profile.refresh_from_db()
        self.assertTrue(self.student.profile.is_approved)
        self.assertEqual(self.student.profile.approved_by, self.staff)

    def test_sababsiz_ruxsat_olinmaydi(self):
        approve(self.student.profile)
        self.client.post(
            reverse('panel:student_approval', args=[self.student.id]),
            {'action': 'revoke', 'reason': ''},
        )
        self.student.profile.refresh_from_db()
        self.assertTrue(
            self.student.profile.is_approved,
            "Sabab o'quvchiga ko'rsatiladi — usiz olib tashlanmasligi kerak",
        )

    def test_sabab_bilan_olinadi(self):
        approve(self.student.profile)
        self.client.post(
            reverse('panel:student_approval', args=[self.student.id]),
            {'action': 'revoke', 'reason': "To'lov kelmadi"},
        )
        self.student.profile.refresh_from_db()
        self.assertFalse(self.student.profile.is_approved)
        self.assertEqual(self.student.profile.rejection_reason, "To'lov kelmadi")

    def test_qayta_ruxsat_berilganda_rad_sababi_tozalanadi(self):
        revoke(self.student.profile, reason='Eski sabab')
        self.client.post(
            reverse('panel:student_approval', args=[self.student.id]), {'action': 'approve'}
        )
        self.student.profile.refresh_from_db()
        self.assertEqual(self.student.profile.rejection_reason, '')

    def test_GET_bilan_ruxsat_bermaydi(self):
        response = self.client.get(reverse('panel:student_approval', args=[self.student.id]))
        self.assertEqual(response.status_code, 405)
        self.student.profile.refresh_from_db()
        self.assertFalse(self.student.profile.is_approved)

    def test_oquvchi_ozidan_ozi_ruxsat_bera_olmaydi(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse('panel:student_approval', args=[self.student.id]), {'action': 'approve'}
        )
        self.assertEqual(response.status_code, 403)
        self.student.profile.refresh_from_db()
        self.assertFalse(self.student.profile.is_approved)


class MonthlyOnlyTests(TestCase):
    """Obuna faqat bir oylik."""

    def test_faqat_bir_oy_ruxsat_etiladi(self):
        from billing import dates

        self.assertEqual(dates.ALLOWED_MONTHS, (1,))

    def test_uch_oylik_sorov_rad_etiladi(self):
        from billing import payment_requests, services

        SubscriptionPlan.objects.create(
            code='T', name='T', price_per_month_tiyin=10_000_000
        )
        user = make_student('uchoylik', approved=True)

        with self.assertRaises(services.BillingError):
            payment_requests.create_request(user, months=3)

    def test_bir_oylik_sorov_otadi(self):
        from billing import payment_requests

        SubscriptionPlan.objects.create(
            code='T', name='T', price_per_month_tiyin=10_000_000
        )
        user = make_student('bironlik', approved=True)

        req = payment_requests.create_request(user, months=1)
        self.assertEqual(req.months, 1)
        self.assertEqual(req.amount_tiyin, 10_000_000)
