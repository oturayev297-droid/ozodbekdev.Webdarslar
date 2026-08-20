"""
Topshiriq natijasini solishtirish testlari.

ASOSIY XAVF — TO'G'RI YECHIMNI RAD ETISH. Bunday xato eng yomoni:
o'quvchi to'g'ri yozgan bo'ladi-yu, dastur "noto'g'ri" deydi va u
xatoni qayerdan qidirishni bilmaydi. Shuning uchun bu yerda ko'proq
"aslida bir xil" holatlar sinaladi.
"""

from django.test import SimpleTestCase

from core import challenge_check as check


class NormalizeTests(SimpleTestCase):
    def test_oxirgi_bosh_qatorlar_hisobga_olinmaydi(self):
        """`print()` har doim qator tashlaydi — u natijaning qismi emas."""
        self.assertTrue(check.compare("Salom\n", "Salom"))
        self.assertTrue(check.compare("Salom", "Salom\n\n\n"))

    def test_windows_qator_ajratgichi_farq_qilmaydi(self):
        self.assertTrue(check.compare("bir\niki", "bir\r\niki"))

    def test_qator_oxiridagi_bosh_joy_kechiriladi(self):
        self.assertTrue(check.compare("Salom", "Salom   "))

    def test_registr_FARQ_QILADI(self):
        """
        Katta-kichik harf natijaning O'ZI. Ularga ko'z yumilsa,
        "salom" bilan "Salom" bir xil bo'lib qolardi va topshiriq
        matnidagi aniq talab ma'nosini yo'qotardi.
        """
        self.assertFalse(check.compare("Salom", "salom"))

    def test_qatorlar_tartibi_FARQ_QILADI(self):
        self.assertFalse(check.compare("bir\niki", "iki\nbir"))

    def test_ortadagi_bosh_qator_farq_qiladi(self):
        self.assertFalse(check.compare("bir\niki", "bir\n\niki"))


class FirstDifferenceTests(SimpleTestCase):
    def test_farq_yoq_bolsa_none(self):
        self.assertIsNone(check.first_difference("bir\niki", "bir\niki\n"))

    def test_qator_raqami_1_dan_boshlanadi(self):
        line, expected, actual = check.first_difference("bir\niki", "bir\nuch")
        self.assertEqual((line, expected, actual), (2, 'iki', 'uch'))

    def test_yetishmayotgan_qator_none_bolib_keladi(self):
        line, expected, actual = check.first_difference("bir\niki", "bir")
        self.assertEqual((line, expected, actual), (2, 'iki', None))

    def test_ortiqcha_qator_ham_farq(self):
        line, expected, actual = check.first_difference("bir", "bir\nortiqcha")
        self.assertEqual((line, expected, actual), (2, None, 'ortiqcha'))


class ErrorDetectionTests(SimpleTestCase):
    def test_python_traceback_topiladi(self):
        self.assertTrue(check.looks_like_error("Traceback (most recent call last):"))

    def test_javascript_xatosi_topiladi(self):
        self.assertTrue(check.looks_like_error("ReferenceError: x is not defined"))

    def test_oddiy_natija_xato_emas(self):
        self.assertFalse(check.looks_like_error("Salom, dunyo!"))
