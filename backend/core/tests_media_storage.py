"""
Rasm va avatarlar uchun bulut ombori testlari.

HAQIQIY SO'ROV YUBORILMAYDI — quyi qatlam (`core.video_storage`)
mock qilinadi. Bu yerda tekshiriladigan narsa tarmoq emas, SHARTNOMA:
Django `Storage` dan nimani kutsa, sinf o'shani bajaradimi.

ENG MUHIM SHART — `_save()` NOMNI O'ZGARTIRMASLIGI kerak. Bazadagi
yo'l bilan bucketdagi kalit bir xil bo'lgani uchun omborni almashtirish
migratsiyasiz kechadi. Nom o'zgarsa, mavjud 83 ta darsning rasmlari
bir zumda "topilmadi" bo'lib qolardi.
"""

from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from core.media_storage import IMAGE_URL_TTL, CloudMediaStorage

CLOUD = dict(
    VIDEO_STORAGE_BUCKET='sinov-bucket',
    VIDEO_STORAGE_ENDPOINT='https://example.r2.cloudflarestorage.com',
    VIDEO_STORAGE_ACCESS_KEY='kalit',
    VIDEO_STORAGE_SECRET_KEY='maxfiy',
    VIDEO_STORAGE_REGION='auto',
)


@override_settings(**CLOUD)
class CloudMediaStorageTests(TestCase):
    def setUp(self):
        self.storage = CloudMediaStorage()

    def test_saqlaganda_nom_ozgarmaydi(self):
        with patch('core.video_storage.save_fileobj') as save:
            name = self.storage._save(
                'lesson_images/sxema.png', ContentFile(b'rasm', name='sxema.png')
            )

        self.assertEqual(name, 'lesson_images/sxema.png')
        self.assertEqual(save.call_args.args[1], 'lesson_images/sxema.png')

    def test_havola_imzolanadi(self):
        with patch('core.video_storage.signed_url', return_value='https://imzo') as signed:
            url = self.storage.url('lesson_images/sxema.png')

        self.assertEqual(url, 'https://imzo')
        self.assertEqual(signed.call_args.kwargs['ttl'], IMAGE_URL_TTL)

    def test_havola_muddati_videonikidan_uzun(self):
        """
        Rasm sahifa ochiq turganda eskirib qolmasligi kerak. Video
        havolasi qisqa: u darsning O'ZI va himoyasi qattiqroq.
        """
        from core import video_storage

        self.assertGreater(IMAGE_URL_TTL, video_storage.DEFAULT_URL_TTL)

    def test_oqish_bulutdan_keladi(self):
        with patch('core.video_storage.read', return_value=b'baytlar'):
            self.assertEqual(self.storage._open('lesson_images/a.png').read(), b'baytlar')

    def test_yozish_uchun_ochib_bolmaydi(self):
        """
        Faylni 'w' bilan ochish xotirada o'zgarish qoldirib, bucketga
        hech qachon qaytarmasdi — jimgina ma'lumot yo'qotish.
        """
        with self.assertRaises(ValueError):
            self.storage._open('lesson_images/a.png', 'wb')

    def test_ochirish_va_hajm_bulutga_uzatiladi(self):
        with patch('core.video_storage.delete') as delete:
            self.storage.delete('lesson_images/a.png')
        delete.assert_called_once_with('lesson_images/a.png')

        with patch('core.video_storage.size', return_value=512):
            self.assertEqual(self.storage.size('lesson_images/a.png'), 512)

    def test_yoq_faylning_hajmi_nol(self):
        """
        `size()` None qaytarsa Django uni solishtira olmasdi va
        `TypeError` bilan yiqilardi.
        """
        with patch('core.video_storage.size', return_value=None):
            self.assertEqual(self.storage.size('yoq.png'), 0)

    def test_nom_toqnashganda_ustiga_yozilmaydi(self):
        """
        Asosiy `Storage` sinfi `exists()` orqali hal qiladi — shu
        ishlayotganini tekshiramiz, aks holda bir xil nomli ikkinchi
        rasm birinchisini bosib ketardi.
        """
        with patch('core.video_storage.exists', side_effect=[True, False]):
            name = self.storage.get_available_name('lesson_images/sxema.png')

        self.assertNotEqual(name, 'lesson_images/sxema.png')
        self.assertTrue(name.startswith('lesson_images/sxema'))
        self.assertTrue(name.endswith('.png'))
