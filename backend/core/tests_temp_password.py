"""
Admin tomonidan parol tiklash.

E'TIBOR QARATILGAN JOYLAR:

  * YANGI PAROL HAQIQATAN ISHLASHI — aks holda admin o'quvchiga
    ishlamaydigan parol aytardi va muammo hal bo'lmasdi
  * ESKI PAROL ISHLAMAY QOLISHI
  * SEANSLAR YOPILISHI — parolni bilib olgan begona odam eski
    seansda qolib ketmasin
  * XODIM hisobiga bu yo'l bilan tegib bo'lmasligi
  * PAROL HECH QAYERDA SAQLANMASLIGI
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core import temp_password
from core.models import PasswordResetLog

OLD_PASSWORD = 'eski-parol-1234567'


def make_student(username='oquvchi'):
    return User.objects.create_user(username, password=OLD_PASSWORD)


def make_staff(username='admin20'):
    user = User.objects.create_user(username, password='juda-maxfiy-parol-8')
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    return user


class GenerateTests(TestCase):
    """Parolning o'zi."""

    def test_chalkashtiradigan_belgilar_yoq(self):
        """
        Parol telefonda OG'ZAKI aytiladi. `0` bilan `O`, `1` bilan `l`
        farqlanmasa, admin uni qayta-qayta takrorlashiga to'g'ri
        kelardi.
        """
        for _ in range(200):
            password = temp_password.generate()
            for bad in '0O1lI':
                self.assertNotIn(bad, password, f"Chalkash belgi: {password}")

    def test_takrorlanmaydi(self):
        passwords = {temp_password.generate() for _ in range(200)}
        self.assertEqual(len(passwords), 200)

    def test_oqilishi_qulay_shaklda(self):
        password = temp_password.generate()
        parts = password.split('-')

        self.assertEqual(len(parts), temp_password.GROUPS)
        for part in parts:
            self.assertEqual(len(part), temp_password.GROUP_SIZE)


class ResetTests(TestCase):
    def setUp(self):
        self.student = make_student()
        self.admin = make_staff()

    def test_YANGI_PAROL_ISHLAYDI(self):
        """
        Eng muhim tekshiruv: butun amalning maqsadi shu. Parol
        ishlamasa, admin o'quvchiga bekorga aytgan bo'lardi.
        """
        password = temp_password.reset(self.student, admin=self.admin)

        self.assertTrue(
            Client().login(username=self.student.username, password=password)
        )

    def test_eski_parol_ishlamaydi(self):
        temp_password.reset(self.student, admin=self.admin)

        self.assertFalse(
            Client().login(username=self.student.username, password=OLD_PASSWORD)
        )

    def test_OCHIQ_SEANSLAR_YOPILADI(self):
        """
        Parolni bilib olgan begona odam allaqachon kirgan bo'lsa,
        parol almashgani uni chiqarib yubormasdi — seans alohida
        yashaydi. Tiklashning ma'nosi aynan shu odamni uzish.
        """
        intruder = Client()
        intruder.force_login(self.student)
        self.assertIn('_auth_user_id', intruder.session)

        temp_password.reset(self.student, admin=self.admin)

        # Eski seans bilan himoyalangan manzil ochilmasligi kerak
        response = intruder.get(reverse('api:me'))
        self.assertEqual(response.status_code, 403)

    def test_boshqa_oquvchining_seansi_yopilmaydi(self):
        other = make_student('boshqa')
        session = Client()
        session.force_login(other)

        temp_password.reset(self.student, admin=self.admin)

        self.assertEqual(session.get(reverse('api:me')).status_code, 200)

    def test_jurnalga_yoziladi(self):
        temp_password.reset(self.student, admin=self.admin)

        log = PasswordResetLog.objects.get(student=self.student)
        self.assertEqual(log.admin, self.admin)

    def test_jurnalda_PAROL_SAQLANMAYDI(self):
        """
        Jurnal parolni saqlasa, ochiq matnda saqlashdan farqi
        qolmasdi — butun yechimning ma'nosi yo'qolardi.
        """
        password = temp_password.reset(self.student, admin=self.admin)

        log = PasswordResetLog.objects.get(student=self.student)
        values = ' '.join(str(v) for v in log.__dict__.values())
        self.assertNotIn(password, values)

    def test_XODIM_hisobiga_tegib_bolmaydi(self):
        """
        Aks holda bir admin ikkinchisining hisobini egallab, undan
        panel huquqini tortib olardi.
        """
        other_admin = make_staff('admin21')

        with self.assertRaises(temp_password.TempPasswordError):
            temp_password.reset(other_admin, admin=self.admin)

    def test_faolsizlantirilgan_hisob_rad_etiladi(self):
        self.student.is_active = False
        self.student.save(update_fields=['is_active'])

        with self.assertRaises(temp_password.TempPasswordError):
            temp_password.reset(self.student, admin=self.admin)


class PanelTests(TestCase):
    """Paneldagi tugma."""

    def setUp(self):
        self.student = make_student()
        self.admin = make_staff()
        self.client.force_login(self.admin)
        self.url = reverse('panel:student_password_reset', args=[self.student.id])

    def test_parol_xabarda_BIR_MARTA_korinadi(self):
        response = self.client.post(self.url, follow=True)

        text = response.content.decode()
        self.assertIn('yangi parol', text.lower())

        # Xabardagi paroldan foydalanib kirish mumkin bo'lishi kerak
        import re
        match = re.search(r'parol: ([A-Za-z2-9]{4}-[A-Za-z2-9]{4}-[A-Za-z2-9]{4})', text)
        self.assertIsNotNone(match, 'Parol xabarda ko\'rinmadi')
        self.assertTrue(
            Client().login(username=self.student.username, password=match.group(1))
        )

    def test_parol_sahifada_QOLMAYDI(self):
        """
        Xabar bir marta ko'rsatiladi. Sahifa yangilansa parol
        yo'qolishi kerak — aks holda u brauzer tarixida qolardi.
        """
        self.client.post(self.url, follow=True)

        again = self.client.get(reverse('panel:student_detail', args=[self.student.id]))
        self.assertNotIn('yangi parol:', again.content.decode().lower())

    def test_oquvchi_bu_tugmani_bosa_olmaydi(self):
        self.client.force_login(make_student('oddiy5'))

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(PasswordResetLog.objects.count(), 0)

    def test_GET_bilan_ishlamaydi(self):
        """
        Parolni almashtirish — o'zgartiruvchi amal. GET bilan
        bajarilsa, sahifadagi rasm havolasi ham uni ishga tushirib
        yuborishi mumkin edi.
        """
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)
        self.assertEqual(PasswordResetLog.objects.count(), 0)

    def test_tarix_sahifada_korinadi(self):
        self.client.post(self.url, follow=True)

        response = self.client.get(reverse('panel:student_detail', args=[self.student.id]))
        self.assertContains(response, 'tikladi')
