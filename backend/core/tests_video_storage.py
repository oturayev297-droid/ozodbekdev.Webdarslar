"""
Video omborini uzatish testlari.

BULUTGA HAQIQIY SO'ROV YUBORILMAYDI — `boto3` mock qilinadi. Testlar
internet, hisob va pulga bog'liq bo'lmasligi kerak.

TEKSHIRILADIGAN ASOSIY NARSA: rejim qanday bo'lishidan qat'i nazar,
HUQUQ har doim Django tomonida tekshiriladi. Bulutga o'tish paywallda
teshik ochib qo'ymasligi kerak.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from billing.models import PeriodSource, SubscriptionPlan
from billing.services import extend_subscription
from core import video_storage
from core.models import Category, Lesson, Module

CLOUD = dict(
    VIDEO_STORAGE_BUCKET='sinov-bucket',
    VIDEO_STORAGE_ENDPOINT='https://example.r2.cloudflarestorage.com',
    VIDEO_STORAGE_ACCESS_KEY='kalit',
    VIDEO_STORAGE_SECRET_KEY='maxfiy',
    VIDEO_STORAGE_REGION='auto',
)


class CloudDetectionTests(TestCase):
    def test_sozlanmagan_holda_ochiq(self):
        with override_settings(VIDEO_STORAGE_BUCKET='', VIDEO_STORAGE_ACCESS_KEY='',
                               VIDEO_STORAGE_SECRET_KEY=''):
            self.assertFalse(video_storage.is_cloud_enabled())

    def test_toliq_sozlanganda_yoqiladi(self):
        with override_settings(**CLOUD):
            self.assertTrue(video_storage.is_cloud_enabled())

    def test_yarim_sozlangan_holat_YOQILMAYDI(self):
        """
        Kalitlarning biri yetishmasa bulut rejimi yoqilmasligi kerak —
        aks holda har video so'rovi imzo xatosi bilan yiqilardi va
        sayt buzilgandek ko'rinardi.
        """
        half = dict(CLOUD)
        half['VIDEO_STORAGE_SECRET_KEY'] = ''
        with override_settings(**half):
            self.assertFalse(video_storage.is_cloud_enabled())

    def test_sozlanmagan_holda_imzo_soralsa_xato(self):
        with override_settings(VIDEO_STORAGE_BUCKET=''):
            with self.assertRaises(video_storage.VideoStorageError):
                video_storage.signed_url('lesson_videos/a.mp4')


@override_settings(**CLOUD)
class SignedUrlTests(TestCase):
    @patch('core.video_storage._client')
    def test_imzolangan_havola_soraladi(self, mock_client):
        client = MagicMock()
        client.generate_presigned_url.return_value = 'https://imzolangan/havola'
        mock_client.return_value = client

        url = video_storage.signed_url('lesson_videos/dars.mp4')

        self.assertEqual(url, 'https://imzolangan/havola')
        kwargs = client.generate_presigned_url.call_args.kwargs
        self.assertEqual(kwargs['Params']['Bucket'], 'sinov-bucket')
        self.assertEqual(kwargs['Params']['Key'], 'lesson_videos/dars.mp4')

    @patch('core.video_storage._client')
    def test_havola_muddati_cheklangan(self, mock_client):
        """Muddatsiz havola tarqatilsa obuna ma'nosini yo'qotardi."""
        client = MagicMock()
        mock_client.return_value = client

        video_storage.signed_url('lesson_videos/dars.mp4')

        ttl = client.generate_presigned_url.call_args.kwargs['ExpiresIn']
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, 24 * 60 * 60, "Havola bir kundan ortiq yashamasin")


class VideoAccessTests(TestCase):
    """Rejimdan qat'i nazar huquq tekshirilishi."""

    def setUp(self):
        SubscriptionPlan.objects.create(code='T', name='T', price_per_month_tiyin=10_000_000)
        category = Category.objects.create(name='Python', slug='python')
        module = Module.objects.create(category=category, title='M', order=1)
        self.paid = Lesson.objects.create(
            module=module, title='Pullik', theory='Matn', order=1, is_free=False,
            video_file='lesson_videos/maxfiy.mp4',
        )
        self.user = User.objects.create_user('talaba', password='juda-maxfiy-parol-8')
        profile = self.user.profile
        profile.is_approved = True
        profile.save(update_fields=['is_approved'])
        self.client.force_login(self.user)

    @override_settings(**CLOUD)
    @patch('core.video_storage._client')
    def test_obunasiz_odam_BULUT_HAVOLASINI_OLMAYDI(self, mock_client):
        """
        Eng muhim tekshiruv: bulutga o'tish paywallni chetlab
        o'tmasligi kerak. Imzolangan havola umuman so'ralmasligi ham
        kerak — so'ralsa, u loglarda qolib ketardi.
        """
        response = self.client.get(reverse('lesson_video', args=[self.paid.id]))

        self.assertEqual(response.status_code, 402)
        mock_client.assert_not_called()

    @override_settings(**CLOUD)
    @patch('core.video_storage._client')
    def test_obunali_odam_havolaga_yonaltiriladi(self, mock_client):
        client = MagicMock()
        client.generate_presigned_url.return_value = 'https://imzolangan/dars.mp4'
        mock_client.return_value = client
        extend_subscription(self.user, days=30, source=PeriodSource.ADMIN_GRANT)

        response = self.client.get(reverse('lesson_video', args=[self.paid.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://imzolangan/dars.mp4')

    @override_settings(VIDEO_STORAGE_BUCKET='', USE_X_ACCEL_REDIRECT=True)
    def test_bulutsiz_nginx_rejimi_ishlaydi(self):
        """Sozlama bo'sh bo'lsa eski yo'l buzilmasligi kerak."""
        extend_subscription(self.user, days=30, source=PeriodSource.ADMIN_GRANT)

        response = self.client.get(reverse('lesson_video', args=[self.paid.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Accel-Redirect'], '/protected/lesson_videos/maxfiy.mp4')
