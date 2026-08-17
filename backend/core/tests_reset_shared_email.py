"""
Bitta emailga bog'langan bir nechta hisob.

NEGA BU HOLAT BOR. Django'da email yagona bo'lishi shart emas va bu
platformada bu ataylab shunday: oilada ota-ona va farzand bitta
pochtadan foydalanishi tabiiy. Amalda ham shunday bo'ldi — bitta
pochtada oltita hisob topildi.

NUQSON. Parol tiklash emaildan topilgan BIRINCHI hisobni olardi:

  * kod doim birinchi hisobga yaratilardi;
  * tasdiqlash ham birinchi hisobni olardi.

Ya'ni qolgan hisoblar parolini HECH QACHON tiklay olmasdi, birinchi
hisob egasi esa boshqalarning kodi bilan o'z parolini almashtirib
olardi.

TUZATILGANI. Har hisobga o'z kodi yaratiladi, xatda qaysi login
uchun qaysi kod ekani ko'rsatiladi, tasdiqlashda esa HISOBNI KOD
ANIQLAYDI — email emas.
"""

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from core import password_reset as pwreset
from core.models import PasswordReset

EMAIL = "oila@example.com"
NEW_PASSWORD = "yangi-kuchli-parol-91"


def make_user(username, email=EMAIL, full_name=''):
    user = User.objects.create_user(username, email=email, password='eski-parol-12345')
    if full_name:
        profile = user.profile
        profile.full_name = full_name
        profile.save(update_fields=['full_name'])
    return user


def codes_from_last_email():
    """Xatdagi `login — kod: NNNNNN` juftliklari."""
    import re
    body = mail.outbox[-1].body
    return dict(re.findall(r'(\S+) — kod: (\d{6})', body))


def single_code_from_last_email():
    import re
    m = re.search(r'kodingiz: (\d{6})', mail.outbox[-1].body)
    return m.group(1) if m else None


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SharedEmailTests(TestCase):
    def setUp(self):
        self.ota = make_user('ota', full_name='Sobir Ahmedov')
        self.bola = make_user('bola', full_name='Diyorbek Sobirov')
        mail.outbox = []

    def test_HAR_HISOBGA_ALOHIDA_kod(self):
        pwreset.request_reset(EMAIL)

        self.assertEqual(PasswordReset.objects.count(), 2)
        self.assertEqual(
            {r.user_id for r in PasswordReset.objects.all()},
            {self.ota.pk, self.bola.pk},
        )

    def test_xatda_qaysi_kod_qaysi_login_uchun_korinadi(self):
        pwreset.request_reset(EMAIL)

        codes = codes_from_last_email()
        self.assertEqual(set(codes), {'ota', 'bola'})
        self.assertNotEqual(codes['ota'], codes['bola'], 'Kodlar bir xil bo\'lmasin')

    def test_bitta_xat_yuboriladi(self):
        """Ikki xat kelsa odam qaysi biri kerakligini bilmasdi."""
        pwreset.request_reset(EMAIL)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [EMAIL])

    def test_IKKINCHI_hisob_ham_parolini_tiklaydi(self):
        """
        ENG MUHIM TEKSHIRUV. Ilgari ikkinchi hisob egasi parolini
        tiklay olmasdi — kod boshqa odamning hisobiga yaratilardi.
        """
        pwreset.request_reset(EMAIL)
        code = codes_from_last_email()['bola']

        pwreset.confirm_reset(EMAIL, code, NEW_PASSWORD)

        self.bola.refresh_from_db()
        self.assertTrue(self.bola.check_password(NEW_PASSWORD))

    def test_BOSHQA_hisob_paroli_TEGILMAYDI(self):
        """
        Ilgari qaysi kod kiritilsa ham birinchi hisobning paroli
        almashardi — ya'ni bola otasining hisobiga kira olardi.
        """
        pwreset.request_reset(EMAIL)
        code = codes_from_last_email()['bola']

        pwreset.confirm_reset(EMAIL, code, NEW_PASSWORD)

        self.ota.refresh_from_db()
        self.assertFalse(
            self.ota.check_password(NEW_PASSWORD),
            "Boshqa hisobning paroli ham almashdi",
        )
        self.assertTrue(self.ota.check_password('eski-parol-12345'))

    def test_birinchi_hisob_ham_ishlaydi(self):
        pwreset.request_reset(EMAIL)
        code = codes_from_last_email()['ota']

        pwreset.confirm_reset(EMAIL, code, NEW_PASSWORD)

        self.ota.refresh_from_db()
        self.assertTrue(self.ota.check_password(NEW_PASSWORD))

    def test_kod_bir_marta_ishlaydi(self):
        pwreset.request_reset(EMAIL)
        code = codes_from_last_email()['bola']
        pwreset.confirm_reset(EMAIL, code, NEW_PASSWORD)

        with self.assertRaises(pwreset.ResetError):
            pwreset.confirm_reset(EMAIL, code, 'boshqa-kuchli-parol-77')

    def test_notogri_kod_HAMMA_urinishini_oshiradi(self):
        """
        Urinish faqat bitta yozuvga yozilsa, hujumchi bir hisobning
        cheklovini boshqasi orqali aylanib o'tardi.
        """
        pwreset.request_reset(EMAIL)

        with self.assertRaises(pwreset.ResetError):
            pwreset.confirm_reset(EMAIL, '000000', NEW_PASSWORD)

        attempts = list(PasswordReset.objects.values_list('attempts', flat=True))
        self.assertEqual(attempts, [1, 1], f"Urinishlar: {attempts}")

    def test_urinishlar_tugagach_kod_kuyadi(self):
        pwreset.request_reset(EMAIL)
        real_code = codes_from_last_email()['bola']

        for _ in range(pwreset.MAX_ATTEMPTS):
            with self.assertRaises(pwreset.ResetError):
                pwreset.confirm_reset(EMAIL, '000000', NEW_PASSWORD)

        # To'g'ri kod ham endi ishlamasligi kerak
        with self.assertRaises(pwreset.ResetError):
            pwreset.confirm_reset(EMAIL, real_code, NEW_PASSWORD)

    def test_faolsizlantirilgan_hisob_kod_olmaydi(self):
        self.bola.is_active = False
        self.bola.save(update_fields=['is_active'])

        pwreset.request_reset(EMAIL)

        self.assertEqual(PasswordReset.objects.count(), 1)
        self.assertEqual(PasswordReset.objects.get().user, self.ota)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SingleAccountTests(TestCase):
    """Bitta hisob — xat matni oddiy va o'zgarmagan bo'lishi kerak."""

    def setUp(self):
        self.user = make_user('yolgiz', email='yolgiz@example.com', full_name='Ali Valiyev')
        mail.outbox = []

    def test_xat_ismga_murojaat_qiladi(self):
        pwreset.request_reset('yolgiz@example.com')

        body = mail.outbox[0].body
        self.assertIn('Ali Valiyev', body)
        self.assertNotIn('ta hisob bog', body, 'Bitta hisobda ro\'yxat ko\'rsatilmasin')

    def test_parol_tiklanadi(self):
        pwreset.request_reset('yolgiz@example.com')
        code = single_code_from_last_email()

        pwreset.confirm_reset('yolgiz@example.com', code, NEW_PASSWORD)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_yoq_email_xat_yubormaydi(self):
        pwreset.request_reset('yoq@example.com')

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(PasswordReset.objects.count(), 0)
