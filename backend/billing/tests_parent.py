"""
Ota-ona obunasi va farzand uchun to'lov.

E'TIBOR QARATILGAN JOYLAR:

  * NARX NOL BO'LSA panel BEPUL qolishi — yangilanish mavjud
    ota-onalarni yopib qo'ymasligi
  * Narx qo'yilgach obunasi yo'q ota-ona hisobotni ko'rmasligi
  * Ota-ona FAQAT o'z farzandi uchun to'lay olishi
  * Farzand uchun to'lov O'QUVCHI tarifida bo'lishi — aks holda
    tushum hisoboti buzilardi
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from billing import parent_billing, services
from billing.models import PaymentMethod, PaymentRequest, PeriodSource
from billing.services import extend_subscription
from core.models import ParentLink


def make_user(username, approved=False):
    user = User.objects.create_user(username, password='juda-maxfiy-parol-4')
    profile = user.profile
    profile.is_approved = approved
    profile.save(update_fields=['is_approved'])
    return user


def set_parent_price(soum):
    plan = services.get_parent_plan()
    plan.price_per_month_tiyin = soum * 100
    plan.save(update_fields=['price_per_month_tiyin'])
    return plan


class ReportGateTests(TestCase):
    def setUp(self):
        self.parent = make_user('ota9')
        self.child = make_user('bola9', approved=True)
        ParentLink.objects.create(parent=self.parent, student=self.child)
        self.url = reverse('api:parent_child_report', args=[self.child.id])
        self.client.force_login(self.parent)

    def test_narx_NOL_bolsa_ochiq(self):
        """
        STANDART HOLAT. Yangilanish bilan birga mavjud ota-onalar
        yopilib qolmasligi kerak — kecha bepul ko'rgan narsani bugun
        ko'rmay qolsa, bu xato deb qabul qilinadi.
        """
        set_parent_price(0)

        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_narx_qoyilsa_obunasizga_YOPIQ(self):
        set_parent_price(30_000)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()['code'], 'PARENT_SUBSCRIPTION_REQUIRED')

    def test_obunasi_borga_ochiq(self):
        set_parent_price(30_000)
        extend_subscription(
            self.parent, months=1, source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CASH, amount_tiyin=3_000_000,
        )

        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_BEGONA_odamga_obuna_ham_yordam_bermaydi(self):
        """
        To'lagan odam ham faqat O'Z farzandini ko'radi. Aks holda
        30 000 so'm to'lab hamma bolaning natijasini ko'rish
        mumkin bo'lardi.
        """
        set_parent_price(30_000)
        extend_subscription(
            self.parent, months=1, source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CASH, amount_tiyin=3_000_000,
        )
        stranger = make_user('begona9', approved=True)

        response = self.client.get(
            reverse('api:parent_child_report', args=[stranger.id])
        )

        self.assertEqual(response.status_code, 403)

    def test_royxatda_obuna_holati_korinadi(self):
        set_parent_price(30_000)

        data = self.client.get(reverse('api:parent_children')).json()

        self.assertTrue(data['reports_are_paid'])
        self.assertFalse(data['can_view_reports'])
        self.assertIn('subscription', data)


class ParentPlanTests(TestCase):
    """Tarif tanlash."""

    def test_ota_onaga_OTA_ONA_tarifi(self):
        parent = make_user('ota10')
        child = make_user('bola10', approved=True)
        ParentLink.objects.create(parent=parent, student=child)

        self.assertEqual(services.plan_for(parent).code, services.PARENT_PLAN_CODE)

    def test_oquvchiga_OQUVCHI_tarifi(self):
        student = make_user('oquvchi10', approved=True)

        self.assertEqual(services.plan_for(student).code, services.PLAN_CODE)

    def test_ham_oquvchi_ham_ota_ona_bolsa_OQUVCHI(self):
        """
        Ikkalasi ham bo'lgan odam o'quvchi hisoblanadi: uning tarifi
        qimmatroq va u darslarni ham oladi. Teskarisi bo'lganda,
        farzandini bog'lab qo'ygan o'quvchi arzon tarifga o'tib,
        darslarni ham olardi.
        """
        both = make_user('ikkisi', approved=True)
        child = make_user('bola11', approved=True)
        ParentLink.objects.create(parent=both, student=child)

        self.assertEqual(services.plan_for(both).code, services.PLAN_CODE)

    def test_ota_ona_tolovi_OTA_ONA_narxida(self):
        set_parent_price(30_000)
        parent = make_user('ota11')
        child = make_user('bola12', approved=True)
        ParentLink.objects.create(parent=parent, student=child)

        result = extend_subscription(
            parent, months=1, source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CASH,
        )

        self.assertEqual(result.period.amount_tiyin, 3_000_000)


class ChildPaymentTests(TestCase):
    """Ota-ona farzandi uchun to'laydi."""

    def setUp(self):
        self.parent = make_user('ota12')
        self.child = make_user('bola13', approved=True)
        ParentLink.objects.create(parent=self.parent, student=self.child)
        self.client.force_login(self.parent)
        self.url = reverse('api:parent_child_pay', args=[self.child.id])

    def test_sorov_FARZAND_nomiga_ochiladi(self):
        response = self.client.post(self.url, {'months': 1})

        self.assertEqual(response.status_code, 201)
        created = PaymentRequest.objects.get()
        self.assertEqual(created.user, self.child)
        self.assertEqual(created.requested_by, self.parent)

    def test_summa_OQUVCHI_tarifida(self):
        """
        Farzand uchun to'lov o'quvchi tarifida bo'lishi kerak — pul
        uning darslarini ochadi. Ota-ona tarifi olinsa, arzon to'lab
        qimmat xizmat olish yo'li ochilardi.
        """
        set_parent_price(30_000)

        self.client.post(self.url, {'months': 1})

        created = PaymentRequest.objects.get()
        self.assertEqual(created.plan.code, services.PLAN_CODE)
        self.assertEqual(
            created.amount_tiyin, services.get_plan().price_per_month_tiyin
        )

    def test_BEGONA_bola_uchun_tolab_bolmaydi(self):
        stranger = make_user('begona12', approved=True)

        response = self.client.post(
            reverse('api:parent_child_pay', args=[stranger.id]), {'months': 1}
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(PaymentRequest.objects.count(), 0)

    def test_takroriy_sorov_ochilmaydi(self):
        self.client.post(self.url, {'months': 1})
        response = self.client.post(self.url, {'months': 1})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(PaymentRequest.objects.count(), 1)

    def test_notogri_muddat_rad_etiladi(self):
        response = self.client.post(self.url, {'months': 99})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(PaymentRequest.objects.count(), 0)

    def test_anonim_tolay_olmaydi(self):
        self.client.logout()

        response = self.client.post(self.url, {'months': 1})

        self.assertEqual(response.status_code, 403)


class PanelParentPriceTests(TestCase):
    """Paneldagi narx."""

    def setUp(self):
        staff = User.objects.create_user('admin30', password='juda-maxfiy-parol-4')
        staff.is_staff = True
        staff.save(update_fields=['is_staff'])
        self.client.force_login(staff)
        self.url = reverse('panel:settings_parent_price')

    def test_narx_saqlanadi(self):
        self.client.post(self.url, {'price': '30000'})

        self.assertEqual(services.get_parent_plan().price_per_month_tiyin, 3_000_000)

    def test_nol_qabul_qilinadi(self):
        """Nol — bepul qilish usuli, xato emas."""
        set_parent_price(30_000)

        self.client.post(self.url, {'price': '0'})

        self.assertEqual(services.get_parent_plan().price_per_month_tiyin, 0)
        self.assertFalse(services.parent_reports_are_paid())

    def test_manfiy_narx_rad_etiladi(self):
        set_parent_price(30_000)

        self.client.post(self.url, {'price': '-5000'})

        self.assertEqual(services.get_parent_plan().price_per_month_tiyin, 3_000_000)

    def test_OQUVCHI_narxiga_tegmaydi(self):
        student_price = services.get_plan().price_per_month_tiyin

        self.client.post(self.url, {'price': '30000'})

        self.assertEqual(services.get_plan().price_per_month_tiyin, student_price)

    def test_oquvchi_narxni_ozgartira_olmaydi(self):
        self.client.force_login(make_user('oddiy12'))

        response = self.client.post(self.url, {'price': '999000'})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(services.get_parent_plan().price_per_month_tiyin, 0)
