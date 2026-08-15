"""
Yozma dars sahifasi testlari.

ENG MUHIMI — QULF. Dars matni va rasmlari qulflangan darsda sahifaga
UMUMAN yuborilmasligi kerak. CSS bilan yashirish yetarli emas: sahifa
manbasini ochgan har kim o'qib olardi va obunaning ma'nosi qolmasdi.
"""

import json
import re
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from billing.models import PeriodSource
from billing.services import extend_subscription
from core.models import Category, Lesson, LessonImage, Module, Profile

#: Testlar HAQIQIY `media/` papkasiga yozmasligi kerak.
#:
#: Django MEDIA_ROOT ni testda AJRATMAYDI: `ImageField.save()` faylni
#: sozlamadagi papkaga tushiradi va u test tugagach ham qoladi. Bir
#: necha yurishdan keyin `media/lesson_images/` bazada yo'q o'nlab
#: fayl bilan to'lib ketardi.
TEST_MEDIA = tempfile.mkdtemp(prefix='nexus-test-media-')


def tearDownModule():
    shutil.rmtree(TEST_MEDIA, ignore_errors=True)

#: 1x1 shaffof PNG — Pillow ochа oladigan eng kichik haqiqiy rasm
TINY_PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6300010000050001'
    '0d0a2db40000000049454e44ae426082'
)

LESSON_TEXT = """
## Sarlavha

Bu **maxfiy** dars matni. Uzunligi test uchun yetarli bo'lishi kerak,
shuning uchun bir necha jumla yozilgan.

- birinchi element
- ikkinchi element
"""


def extract_course_data(response) -> dict:
    """Sahifaga joylangan JSON ni ajratib oladi."""
    html = response.content.decode()
    match = re.search(r"JSON\.parse\('(.*?)'\);", html, re.S)
    if not match:
        raise AssertionError("Sahifada courseData topilmadi")
    raw = match.group(1)
    # `escapejs` qo'ygan qochirishlarni yechamiz
    return json.loads(raw.encode().decode('unicode_escape').encode('latin1').decode('utf-8'))


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class LessonContentTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Sun'iy intellekt", slug='ai')
        module = Module.objects.create(category=self.category, title='Modul', order=1)

        self.free = Lesson.objects.create(
            module=module, title='Bepul dars', theory=LESSON_TEXT, order=1, is_free=True
        )
        self.paid = Lesson.objects.create(
            module=module, title='Pulli dars', theory=LESSON_TEXT, order=2, is_free=False
        )

        for lesson in (self.free, self.paid):
            image = LessonImage(lesson=lesson, caption='Sxema', order=1)
            image.image.save(f'{lesson.pk}.png', ContentFile(TINY_PNG), save=False)
            image.save()

        self.user = User.objects.create_user('oquvchi', password='juda-maxfiy-parol-1')
        Profile.objects.get_or_create(user=self.user)
        self.client.force_login(self.user)

    def _lessons(self):
        response = self.client.get(reverse('lessons'))
        self.assertEqual(response.status_code, 200)
        return extract_course_data(response)['ai']['lessons']

    # ────────────────── Obunasiz ──────────────────

    def test_bepul_darsning_matni_keladi(self):
        free = self._lessons()[0]
        self.assertTrue(free['unlocked'])
        self.assertTrue(free['hasText'])
        self.assertIn('<strong>maxfiy</strong>', free['theoryHtml'])

    def test_bepul_darsning_rasmi_keladi(self):
        free = self._lessons()[0]
        self.assertEqual(len(free['images']), 1)
        self.assertEqual(free['images'][0]['caption'], 'Sxema')

    def test_qulflangan_darsning_matni_UMUMAN_yuborilmaydi(self):
        paid = self._lessons()[1]
        self.assertFalse(paid['unlocked'])
        self.assertFalse(paid['hasText'])
        self.assertEqual(paid['theoryHtml'], '')

    def test_qulflangan_darsning_rasmlari_yuborilmaydi(self):
        """Dars mazmuni rasmda bo'lsa, uni qoldirish qulfni ma'nosiz qilardi."""
        paid = self._lessons()[1]
        self.assertEqual(paid['images'], [])

    def test_maxfiy_matn_sahifa_manbasida_yoq(self):
        """Eng to'g'ridan-to'g'ri tekshiruv: butun HTML ichida qidiramiz."""
        response = self.client.get(reverse('lessons'))
        html = response.content.decode()
        # Bepul darsda bu matn bor, lekin u ATAYLAB ochiq. Pulli darsning
        # rasmi manzili esa umuman uchramasligi kerak.
        self.assertNotIn(f'/media/lesson_images/{self.paid.pk}.png', html)

    def test_qulflangan_darsning_sarlavhasi_KO_RINADI(self):
        """O'quvchi nima sotib olayotganini bilishi kerak."""
        paid = self._lessons()[1]
        self.assertEqual(paid['title'], 'Pulli dars')

    # ────────────────── Obuna bilan ──────────────────

    def test_obunachi_hamma_matnni_oladi(self):
        extend_subscription(self.user, days=30, source=PeriodSource.ADMIN_GRANT)

        for lesson in self._lessons():
            with self.subTest(lesson=lesson['title']):
                self.assertTrue(lesson['unlocked'])
                self.assertTrue(lesson['hasText'])
                self.assertEqual(len(lesson['images']), 1)


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class LessonDescriptionTests(TestCase):
    """Kartochkadagi qisqa tavsif bezak belgilaridan tozalanishi."""

    def setUp(self):
        category = Category.objects.create(name='Test', slug='ai')
        module = Module.objects.create(category=category, title='M', order=1)
        Lesson.objects.create(
            module=module, title='Dars', theory=LESSON_TEXT, order=1, is_free=True
        )
        user = User.objects.create_user('o2', password='juda-maxfiy-parol-2')
        Profile.objects.get_or_create(user=user)
        self.client.force_login(user)

    def test_tavsifda_bezak_belgilari_yoq(self):
        response = self.client.get(reverse('lessons'))
        description = extract_course_data(response)['ai']['lessons'][0]['description']
        for marker in ('##', '**', '- '):
            self.assertNotIn(marker, description)

    def test_bolim_tavsifi_yuboriladi(self):
        Category.objects.filter(slug='ai').update(description='Bo\'lim haqida')
        response = self.client.get(reverse('lessons'))
        self.assertEqual(extract_course_data(response)['ai']['description'], "Bo'lim haqida")
