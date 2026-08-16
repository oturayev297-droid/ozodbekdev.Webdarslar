"""
O'quv vaqti va ota-ona paneli testlari.

IKKI XAVF QO'RIQLANADI:

1. VAQTNI SOXTALASHTIRISH. Raqam ota-onaga ko'rsatiladi va u shunga
   qarab qaror qabul qiladi. Skript yozib "kuniga 8 soat" deb yozib
   qo'yish mumkin bo'lsa, butun hisobot ma'nosini yo'qotadi.

2. BEGONA BOLANING MA'LUMOTI. Ota-ona faqat O'ZIGA biriktirilgan
   o'quvchining hisobotini ko'rishi kerak — bu shaxsiy ma'lumot.
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core import study_time
from core.models import ParentLink, StudySession


def make_user(username, approved=True):
    user = User.objects.create_user(username, password='juda-maxfiy-parol-6')
    profile = user.profile
    profile.is_approved = approved
    profile.save(update_fields=['is_approved'])
    return user


class PingTests(TestCase):
    """Signalni yozish qoidalari."""

    def setUp(self):
        self.user = make_user('oquvchi')

    def test_birinchi_signal_yoziladi(self):
        result = study_time.record_ping(self.user)

        self.assertTrue(result['counted'])
        self.assertEqual(result['seconds_today'], study_time.SECONDS_PER_PING)

    def test_juda_tez_kelgan_signal_HISOBGA_OLINMAYDI(self):
        """
        Eng muhim himoya: skript yozib sekundiga o'nlab signal
        yuborish bilan soatlab vaqt to'plash mumkin bo'lmasin.
        """
        study_time.record_ping(self.user)
        result = study_time.record_ping(self.user)

        self.assertFalse(result['counted'])
        self.assertEqual(result['reason'], 'too_soon')
        self.assertEqual(result['seconds_today'], study_time.SECONDS_PER_PING)

    def test_yetarli_vaqt_otgach_yoziladi(self):
        study_time.record_ping(self.user)

        # Oxirgi yozuv vaqtini orqaga suramiz
        StudySession.objects.filter(user=self.user).update(
            updated_at=timezone.now() - timedelta(seconds=study_time.MIN_INTERVAL_SECONDS + 5)
        )

        result = study_time.record_ping(self.user)
        self.assertTrue(result['counted'])
        self.assertEqual(result['seconds_today'], study_time.SECONDS_PER_PING * 2)

    def test_kunlik_chegara_bor(self):
        """Texnik nosozlik tufayli bir kunda 24 soatdan ko'p yozilmasin."""
        StudySession.objects.create(
            user=self.user,
            date=study_time.today(),
            seconds=study_time.MAX_SECONDS_PER_DAY,
        )
        StudySession.objects.filter(user=self.user).update(
            updated_at=timezone.now() - timedelta(minutes=10)
        )

        result = study_time.record_ping(self.user)

        self.assertFalse(result['counted'])
        self.assertEqual(result['reason'], 'daily_limit')

    def test_har_kun_alohida_yozuv(self):
        StudySession.objects.create(
            user=self.user, date=study_time.today() - timedelta(days=1), seconds=600
        )
        study_time.record_ping(self.user)

        self.assertEqual(StudySession.objects.filter(user=self.user).count(), 2)

    def test_dars_tugatilgani_yoziladi(self):
        study_time.record_lesson_completed(self.user)
        study_time.record_lesson_completed(self.user)

        row = StudySession.objects.get(user=self.user, date=study_time.today())
        self.assertEqual(row.lessons_completed, 2)


class SeriesTests(TestCase):
    def setUp(self):
        self.user = make_user('oquvchi2')

    def test_yozuvi_yoq_kun_ham_qatorda_boladi(self):
        """
        Bo'sh kun tushib qolsa grafik tanaffusni ko'rsatmasdi —
        ota-ona esa aynan shuni ko'rmoqchi.
        """
        StudySession.objects.create(
            user=self.user, date=study_time.today() - timedelta(days=3), seconds=1800
        )

        series = study_time.daily_series(self.user, days=7)

        self.assertEqual(len(series), 7)
        self.assertEqual(sum(1 for d in series if d['seconds'] > 0), 1)

    def test_ortacha_FAQAT_faol_kunlar_boyicha(self):
        """
        Nol kunlarni qo'shsak, bir kun 3 soat o'qigan bola "kuniga
        6 daqiqa" bo'lib ko'rinardi va bu chalg'itardi.
        """
        StudySession.objects.create(
            user=self.user, date=study_time.today(), seconds=3600
        )

        result = study_time.summary(self.user, days=30)

        self.assertEqual(result['active_days'], 1)
        self.assertEqual(result['average_minutes'], 60)

    def test_bosh_holatda_yiqilmaydi(self):
        result = study_time.summary(self.user)

        self.assertEqual(result['active_days'], 0)
        self.assertEqual(result['average_minutes'], 0)


class PingApiTests(TestCase):
    def setUp(self):
        self.user = make_user('oquvchi3')
        self.client.force_login(self.user)

    def test_signal_qabul_qilinadi(self):
        response = self.client.post(reverse('api:study_ping'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['counted'])

    def test_klient_MIQDORNI_belgilay_olmaydi(self):
        """
        Soxta `seconds` yuborilsa ham server o'zining qat'iy
        miqdorini qo'shadi. Aks holda bitta so'rov bilan istalgancha
        vaqt yozib olinardi.
        """
        self.client.post(
            reverse('api:study_ping'),
            data='{"seconds": 99999}',
            content_type='application/json',
        )

        row = StudySession.objects.get(user=self.user)
        self.assertEqual(row.seconds, study_time.SECONDS_PER_PING)

    def test_ruxsatsiz_oquvchi_vaqt_yoza_olmaydi(self):
        self.client.force_login(make_user('ruxsatsiz', approved=False))
        response = self.client.post(reverse('api:study_ping'))

        self.assertEqual(response.status_code, 403)
        self.assertFalse(StudySession.objects.filter(user__username='ruxsatsiz').exists())

    def test_anonim_vaqt_yoza_olmaydi(self):
        self.client.logout()
        self.assertEqual(self.client.post(reverse('api:study_ping')).status_code, 403)


class ParentAccessTests(TestCase):
    """Ota-ona FAQAT o'ziga biriktirilgan bolani ko'rishi."""

    def setUp(self):
        self.parent = make_user('otasi', approved=False)
        self.child = make_user('farzand')
        self.other_child = make_user('begonabola')

        ParentLink.objects.create(
            parent=self.parent, student=self.child, relation='Otasi'
        )
        self.client.force_login(self.parent)

    def test_farzandlar_royxati(self):
        response = self.client.get(reverse('api:parent_children'))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['username'], 'farzand')

    def test_oz_farzandining_hisoboti_ochiladi(self):
        response = self.client.get(
            reverse('api:parent_child_report', args=[self.child.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['student']['username'], 'farzand')

    def test_BEGONA_bolaning_hisoboti_YOPIQ(self):
        """
        Eng muhim tekshiruv: ro'yxatdan olingan id ni o'zgartirib
        boshqa bolaning hisobotini ko'rish imkoni bo'lmasligi kerak.
        """
        response = self.client.get(
            reverse('api:parent_child_report', args=[self.other_child.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_bogliqligi_yoq_odam_royxatni_bosh_koradi(self):
        self.client.force_login(make_user('begonaodam'))
        response = self.client.get(reverse('api:parent_children'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_ota_onaga_DARS_RUXSATI_kerak_emas(self):
        """
        Ota-ona o'quvchi emas — unga `is_approved` kerak emas.
        Talab qilinsa, u hisobotni umuman ko'rmasdi.
        """
        self.assertFalse(self.parent.profile.is_approved)
        self.assertEqual(self.client.get(reverse('api:parent_children')).status_code, 200)

    def test_anonim_kira_olmaydi(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('api:parent_children')).status_code, 403)

    def test_hisobotda_vaqt_va_natijalar_bor(self):
        StudySession.objects.create(
            user=self.child, date=study_time.today(), seconds=3600, lessons_completed=2
        )

        response = self.client.get(
            reverse('api:parent_child_report', args=[self.child.id])
        )
        data = response.json()

        self.assertEqual(data['study']['summary']['today_minutes'], 60)
        self.assertEqual(len(data['study']['series']), 14)
        self.assertIn('quizzes', data)
        self.assertIn('lessons', data)


class ParentPanelTests(TestCase):
    """Paneldagi bog'lash."""

    def setUp(self):
        self.staff = User.objects.create_user(
            'admin10', password='juda-maxfiy-parol-6', is_staff=True
        )
        self.client.force_login(self.staff)
        self.parent = make_user('otasi2')
        self.child = make_user('farzand2')

    def test_boglanish_yaratiladi(self):
        self.client.post(reverse('panel:parent_link_create'), {
            'parent': self.parent.id,
            'student': self.child.id,
            'relation': 'Otasi',
        })

        self.assertTrue(
            ParentLink.objects.filter(parent=self.parent, student=self.child).exists()
        )

    def test_ozini_oziga_boglab_bolmaydi(self):
        self.client.post(reverse('panel:parent_link_create'), {
            'parent': self.child.id,
            'student': self.child.id,
        })
        self.assertEqual(ParentLink.objects.count(), 0)

    def test_takroriy_boglanish_yaratilmaydi(self):
        for _ in range(2):
            self.client.post(reverse('panel:parent_link_create'), {
                'parent': self.parent.id,
                'student': self.child.id,
            })
        self.assertEqual(ParentLink.objects.count(), 1)

    def test_boglanish_uziladi(self):
        link = ParentLink.objects.create(parent=self.parent, student=self.child)
        self.client.post(reverse('panel:parent_link_delete', args=[link.pk]))

        self.assertFalse(ParentLink.objects.filter(pk=link.pk).exists())

    def test_oquvchi_boglanish_yarata_olmaydi(self):
        """Aks holda har kim istagan bolaning natijalarini ko'rib olardi."""
        self.client.force_login(self.parent)
        response = self.client.post(reverse('panel:parent_link_create'), {
            'parent': self.parent.id,
            'student': self.child.id,
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(ParentLink.objects.count(), 0)
