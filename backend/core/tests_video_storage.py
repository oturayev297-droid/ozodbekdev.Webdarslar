"""
Video omborini uzatish testlari.

BULUTGA HAQIQIY SO'ROV YUBORILMAYDI — `boto3` mock qilinadi. Testlar
internet, hisob va pulga bog'liq bo'lmasligi kerak.

TEKSHIRILADIGAN ASOSIY NARSA: rejim qanday bo'lishidan qat'i nazar,
HUQUQ har doim Django tomonida tekshiriladi. Bulutga o'tish paywallda
teshik ochib qo'ymasligi kerak.
"""

import time
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from billing.models import PeriodSource, SubscriptionPlan
from billing.services import extend_subscription
from core import video_storage, video_token
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
    """
    Rejimdan qat'i nazar huquq tekshirilishi.

    Session ISHLATILMAYDI: frontend boshqa domenda va `<video>` cookie
    yubormaydi. Pullik darsni `?t=` token ochadi, bepul dars ochiq.
    """

    def setUp(self):
        SubscriptionPlan.objects.create(code='T', name='T', price_per_month_tiyin=10_000_000)
        category = Category.objects.create(name='Python', slug='python')
        module = Module.objects.create(category=category, title='M', order=1)
        self.paid = Lesson.objects.create(
            module=module, title='Pullik', theory='Matn', order=1, is_free=False,
            video_file='lesson_videos/maxfiy.mp4',
        )
        self.free = Lesson.objects.create(
            module=module, title='Bepul', theory='Matn', order=2, is_free=True,
            video_file='lesson_videos/ochiq.mp4',
        )
        self.user = User.objects.create_user('talaba', password='juda-maxfiy-parol-8')
        profile = self.user.profile
        profile.is_approved = True
        profile.save(update_fields=['is_approved'])

    def _get(self, lesson, token=None):
        """Tizimga KIRMAGAN brauzer — `<video>` aynan shunday so'raydi."""
        params = {'t': token} if token is not None else {}
        return self.client.get(reverse('lesson_video', args=[lesson.id]), params)

    def _mock_signed(self, mock_client, url='https://imzolangan/dars.mp4'):
        client = MagicMock()
        client.generate_presigned_url.return_value = url
        mock_client.return_value = client

    @override_settings(**CLOUD)
    @patch('core.video_storage._client')
    def test_tokensiz_odam_BULUT_HAVOLASINI_OLMAYDI(self, mock_client):
        """
        Eng muhim tekshiruv: bulutga o'tish paywallni chetlab
        o'tmasligi kerak. Imzolangan havola umuman so'ralmasligi ham
        kerak — so'ralsa, u loglarda qolib ketardi.
        """
        response = self._get(self.paid)

        self.assertEqual(response.status_code, 403)
        mock_client.assert_not_called()

    @override_settings(**CLOUD)
    @patch('core.video_storage._client')
    def test_session_yetmaydi_token_kerak(self, mock_client):
        """Obunali odam ham tokensiz ololmaydi — huquqni API tekshiradi."""
        extend_subscription(self.user, days=30, source=PeriodSource.ADMIN_GRANT)
        self.client.force_login(self.user)

        response = self._get(self.paid)

        self.assertEqual(response.status_code, 403)
        mock_client.assert_not_called()

    @override_settings(**CLOUD)
    @patch('core.video_storage._client')
    def test_token_bilan_R2_ga_yonaltiriladi(self, mock_client):
        self._mock_signed(mock_client)

        response = self._get(self.paid, video_token.make(self.paid.id, self.user.id))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://imzolangan/dars.mp4')

    @override_settings(**CLOUD)
    @patch('core.video_storage._client')
    def test_bepul_dars_login_va_tokensiz_R2_ga_yonaltiriladi(self, mock_client):
        """Asosiy bug: ilgari bu yerda 302 -> /panel/login/ qaytardi."""
        self._mock_signed(mock_client, 'https://imzolangan/ochiq.mp4')

        response = self._get(self.free)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://imzolangan/ochiq.mp4')

    @override_settings(**CLOUD)
    @patch('core.video_storage._client')
    def test_muddati_otgan_token_rad_etiladi(self, mock_client):
        past = time.time() - video_token.TOKEN_TTL - 60
        with patch('django.core.signing.time.time', return_value=past):
            token = video_token.make(self.paid.id, self.user.id)

        response = self._get(self.paid, token)

        self.assertEqual(response.status_code, 403)
        mock_client.assert_not_called()

    @override_settings(**CLOUD)
    @patch('core.video_storage._client')
    def test_boshqa_dars_tokeni_rad_etiladi(self, mock_client):
        """27-dars tokeni 28-darsni ochmasligi kerak."""
        response = self._get(self.paid, video_token.make(self.free.id, self.user.id))

        self.assertEqual(response.status_code, 403)
        mock_client.assert_not_called()

    @override_settings(**CLOUD)
    @patch('core.video_storage._client')
    def test_soxta_token_rad_etiladi(self, mock_client):
        token = video_token.make(self.paid.id, self.user.id)
        # Imzo o'zgarmagan, lekin foydalanuvchi qismi qalbakilashtirilgan
        forged = token.replace(f"{self.paid.id}:{self.user.id}:", f"{self.paid.id}:999:", 1)

        for bad in ('', 'abc', forged):
            with self.subTest(token=bad):
                self.assertEqual(self._get(self.paid, bad).status_code, 403)
        mock_client.assert_not_called()

    @override_settings(VIDEO_STORAGE_BUCKET='', USE_X_ACCEL_REDIRECT=True)
    def test_bulutsiz_nginx_rejimi_ishlaydi(self):
        """Sozlama bo'sh bo'lsa eski yo'l buzilmasligi kerak."""
        response = self._get(self.paid, video_token.make(self.paid.id, self.user.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Accel-Redirect'], '/protected/lesson_videos/maxfiy.mp4')
