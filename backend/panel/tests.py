"""
Panel testlari
==============

E'TIBOR QARATILGAN JOYLAR:

  * KIRISH — oddiy o'quvchi panelni ochib bo'lmasligi (eng muhimi)
  * HISOBOT — bepul berilgan davrlar tushumga QO'SHILMASLIGI
  * XABAR — takror yuborilmasligi va uzilgandan keyin davom etishi
  * TO'LOV — panel biznes mantiqni chetlab o'tmasligi
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.dates import now as billing_now
from billing.models import (
    PaymentMethod,
    PaymentRequest,
    PeriodSource,
    RequestStatus,
    Subscription,
    SubscriptionPeriod,
    SubscriptionPlan,
)
from billing.services import extend_subscription
from core.models import Category, Lesson, Module, Profile, Quiz

from . import messaging, reports
from .models import Audience, MessageStatus, PanelDelivery, PanelMessage


def make_plan():
    return SubscriptionPlan.objects.create(
        code='TEST', name='Test tarif', price_per_month_tiyin=9_900_000
    )


def make_user(username, staff=False, chat_id=''):
    user = User.objects.create_user(
        username=username, password='juda-maxfiy-parol-123', email=f'{username}@example.com'
    )
    if staff:
        user.is_staff = True
        user.save(update_fields=['is_staff'])
    Profile.objects.update_or_create(user=user, defaults={'telegram_chat_id': chat_id})
    return user


# ══════════════════════════ Kirish huquqi ══════════════════════════


class AccessTests(TestCase):
    """Panelga faqat xodim kira olishi."""

    def setUp(self):
        self.staff = make_user('admin1', staff=True)
        self.student = make_user('oquvchi1')

    def test_anonim_login_sahifasiga_yuboriladi(self):
        response = self.client.get(reverse('panel:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('panel:login'), response['Location'])

    def test_oquvchi_403_oladi_login_sahifasiga_EMAS(self):
        """
        Eng muhim tekshiruv: kirgan o'quvchi login sahifasiga
        qaytarilsa, u to'g'ri parolini kiritib turib cheksiz aylanardi.
        """
        self.client.force_login(self.student)
        response = self.client.get(reverse('panel:dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_xodim_kiradi(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('panel:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_huquq_har_sorovda_tekshiriladi(self):
        """Xodimlik olib tashlansa, ochiq seans ham darhol yopiladi."""
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('panel:dashboard')).status_code, 200)

        self.staff.is_staff = False
        self.staff.save(update_fields=['is_staff'])

        self.assertEqual(self.client.get(reverse('panel:dashboard')).status_code, 403)

    def test_faolsizlantirilgan_xodim_kira_olmaydi(self):
        """
        `is_active=False` bo'lganda Django seansni O'ZI bekor qiladi
        (`ModelBackend.get_user` faolsiz foydalanuvchini qaytarmaydi),
        shuning uchun natija 403 emas, login sahifasiga qaytarish
        bo'ladi. Muhimi — panel ochilmasligi.
        """
        self.client.force_login(self.staff)
        self.staff.is_active = False
        self.staff.save(update_fields=['is_active'])

        response = self.client.get(reverse('panel:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('panel:login'), response['Location'])

    def test_faolsizlantirilgan_xodim_qayta_kira_olmaydi(self):
        """Login sahifasiga tushgani bilan u yerdan ham o'ta olmasligi kerak."""
        self.staff.is_active = False
        self.staff.save(update_fields=['is_active'])

        response = self.client.post(
            reverse('panel:login'),
            {'username': self.staff.username, 'password': 'juda-maxfiy-parol-123'},
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_barcha_sahifalar_himoyalangan(self):
        """Bitta sahifa ham ochiq qolib ketmasin."""
        self.client.force_login(self.student)
        for name in (
            'dashboard', 'finance', 'periods', 'payments', 'gateways',
            'students', 'content', 'quizzes', 'messages', 'monitor',
        ):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f'panel:{name}')).status_code, 403)


class LoginTests(TestCase):
    """Kirish formasi."""

    def setUp(self):
        self.staff = make_user('admin2', staff=True)
        self.student = make_user('oquvchi2')
        self.url = reverse('panel:login')

    def test_togri_parol_bilan_kiradi(self):
        response = self.client.post(
            self.url, {'username': 'admin2', 'password': 'juda-maxfiy-parol-123'}
        )
        self.assertRedirects(response, reverse('panel:dashboard'))

    def test_oquvchi_togri_parol_bilan_ham_kira_olmaydi(self):
        response = self.client.post(
            self.url, {'username': 'oquvchi2', 'password': 'juda-maxfiy-parol-123'}
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_xodim_ekani_oshkor_qilinmaydi(self):
        """
        Parol to'g'ri, lekin hisob xodim emas — xabar parol xato
        bo'lgandagi bilan AYNAN BIR XIL bo'lishi kerak. Aks holda panel
        "qaysi hisob admin" degan savolga javob beradigan asbob bo'lardi.
        """
        wrong = self.client.post(self.url, {'username': 'oquvchi2', 'password': 'notogri'})
        right = self.client.post(
            self.url, {'username': 'oquvchi2', 'password': 'juda-maxfiy-parol-123'}
        )
        self.assertEqual(
            self._error_text(wrong), self._error_text(right),
            "Xodim bo'lmagan hisob uchun xabar boshqacha — bu ma'lumot oshkor qiladi",
        )

    def _error_text(self, response):
        return [m.message for m in response.context['messages']]

    def test_begona_manzilga_yonaltirmaydi(self):
        response = self.client.post(
            self.url,
            {
                'username': 'admin2',
                'password': 'juda-maxfiy-parol-123',
                'next': 'https://yovuz-sayt.example/',
            },
        )
        self.assertRedirects(response, reverse('panel:dashboard'))

    def test_ichki_manzilga_yonaltiradi(self):
        response = self.client.post(
            self.url,
            {
                'username': 'admin2',
                'password': 'juda-maxfiy-parol-123',
                'next': reverse('panel:finance'),
            },
        )
        self.assertRedirects(response, reverse('panel:finance'))

    def test_chiqish_faqat_POST(self):
        """GET bilan chiqarish mumkin bo'lsa, begona saytdagi rasm adminni chiqarardi."""
        self.client.force_login(self.staff)
        self.client.get(reverse('panel:logout'))
        self.assertIn('_auth_user_id', self.client.session)

        self.client.post(reverse('panel:logout'))
        self.assertNotIn('_auth_user_id', self.client.session)


# ══════════════════════════ Hisobot ══════════════════════════


class RevenueTests(TestCase):
    """Tushum hisobotining moliyaviy qoidalari."""

    def setUp(self):
        self.plan = make_plan()
        self.user = make_user('tolovchi')

    def _pay(self, amount=9_900_000, months=1):
        return extend_subscription(
            self.user,
            months=months,
            source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CASH,
            amount_tiyin=amount,
        )

    def test_tolov_tushumga_kiradi(self):
        self._pay()
        summary = reports.revenue_between(
            billing_now() - timedelta(days=1), billing_now() + timedelta(days=1)
        )
        self.assertEqual(summary['total_tiyin'], 9_900_000)
        self.assertEqual(summary['count'], 1)

    def test_bepul_berilgan_davr_tushumga_KIRMAYDI(self):
        """
        Eng muhim moliyaviy qoida. Buzilsa oylik tushum o'ylab topilgan
        raqamga aylanadi.
        """
        extend_subscription(self.user, days=30, source=PeriodSource.ADMIN_GRANT)

        summary = reports.revenue_between(
            billing_now() - timedelta(days=1), billing_now() + timedelta(days=1)
        )
        self.assertEqual(summary['total_tiyin'], 0)
        self.assertEqual(summary['count'], 0)

        # Lekin bepul berilgani ALOHIDA ko'rinadi
        self.assertEqual(reports.granted_summary()['admin_grant'], 1)

    def test_sinov_muddati_ham_tushum_emas(self):
        extend_subscription(self.user, days=7, source=PeriodSource.TRIAL)
        summary = reports.revenue_between(
            billing_now() - timedelta(days=1), billing_now() + timedelta(days=1)
        )
        self.assertEqual(summary['total_tiyin'], 0)

    def test_narx_ozgarsa_otgan_tushum_ozgarmaydi(self):
        """
        Summa davrga muzlatib yozilgani uchun tarif narxi ko'tarilsa ham
        o'tgan oyning raqami o'zgarmasligi kerak.
        """
        self._pay(amount=9_900_000)
        before = reports.revenue_between(
            billing_now() - timedelta(days=1), billing_now() + timedelta(days=1)
        )['total_tiyin']

        self.plan.price_per_month_tiyin = 20_000_000
        self.plan.save(update_fields=['price_per_month_tiyin'])

        after = reports.revenue_between(
            billing_now() - timedelta(days=1), billing_now() + timedelta(days=1)
        )['total_tiyin']
        self.assertEqual(before, after)

    def test_oylik_qator_bosh_oylarni_ham_beradi(self):
        """To'lovi yo'q oy qatordan tushib qolsa grafik yolg'on ko'rinardi."""
        series = reports.monthly_series(months=6)
        self.assertEqual(len(series), 6)
        self.assertTrue(all('total_tiyin' in row for row in series))

    def test_usullar_kesimi(self):
        self._pay()
        rows = reports.method_breakdown()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['method'], PaymentMethod.CASH)
        self.assertEqual(rows[0]['percent'], 100.0)

    def test_kutayotgan_sorov_tushum_emas(self):
        """So'rov — bu NIYAT. Tasdiqlanmaguncha pul hisobga olinmaydi."""
        PaymentRequest.objects.create(
            user=self.user,
            plan=self.plan,
            months=1,
            amount_tiyin=9_900_000,
            status=RequestStatus.RECEIPT_UPLOADED,
            expires_at=timezone.now() + timedelta(days=7),
        )

        summary = reports.revenue_between(
            billing_now() - timedelta(days=1), billing_now() + timedelta(days=1)
        )
        self.assertEqual(summary['total_tiyin'], 0)

        pending = reports.pending_requests()
        self.assertEqual(pending['needs_action'], 1)
        self.assertEqual(pending['receipt_uploaded']['total_tiyin'], 9_900_000)


class SubscriberCountTests(TestCase):
    def setUp(self):
        self.plan = make_plan()

    def test_holat_sanadan_hisoblanadi(self):
        active = make_user('faol')
        expired = make_user('tugagan')

        extend_subscription(active, days=30, source=PeriodSource.ADMIN_GRANT)
        extend_subscription(expired, days=30, source=PeriodSource.ADMIN_GRANT)
        # Muddatni o'tgan sanaga surib qo'yamiz
        Subscription.objects.filter(user=expired).update(
            current_period_end=billing_now() - timedelta(days=5)
        )

        counts = reports.subscriber_counts()
        self.assertEqual(counts['active'], 1)
        self.assertEqual(counts['expired'], 1)


# ══════════════════════════ To'lov amallari ══════════════════════════


class PaymentActionTests(TestCase):
    """Panel biznes mantiqni chetlab o'tmasligi."""

    def setUp(self):
        self.plan = make_plan()
        self.staff = make_user('admin3', staff=True)
        self.student = make_user('tolovchi2')
        self.client.force_login(self.staff)

        self.req = PaymentRequest.objects.create(
            user=self.student,
            plan=self.plan,
            months=1,
            amount_tiyin=9_900_000,
            status=RequestStatus.RECEIPT_UPLOADED,
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_tasdiqlash_obunani_uzaytiradi_va_jurnalga_yozadi(self):
        self.client.post(
            reverse('panel:payment_action', args=[self.req.pk]),
            {'action': 'confirm', 'payment_method': PaymentMethod.CASH},
        )

        self.req.refresh_from_db()
        self.assertEqual(self.req.status, RequestStatus.CONFIRMED)

        period = SubscriptionPeriod.objects.get(payment_request=self.req)
        self.assertEqual(period.source, PeriodSource.PAYMENT)
        self.assertEqual(period.amount_tiyin, 9_900_000)

        subscription = Subscription.objects.get(user=self.student)
        self.assertIsNotNone(subscription.current_period_end)

    def test_ikki_marta_tasdiqlash_obunani_ikki_marta_uzaytirmaydi(self):
        url = reverse('panel:payment_action', args=[self.req.pk])
        self.client.post(url, {'action': 'confirm', 'payment_method': PaymentMethod.CASH})
        end_after_first = Subscription.objects.get(user=self.student).current_period_end

        self.client.post(url, {'action': 'confirm', 'payment_method': PaymentMethod.CASH})

        self.assertEqual(
            Subscription.objects.get(user=self.student).current_period_end, end_after_first
        )
        self.assertEqual(SubscriptionPeriod.objects.filter(payment_request=self.req).count(), 1)

    def test_sababsiz_rad_etilmaydi(self):
        self.client.post(
            reverse('panel:payment_action', args=[self.req.pk]),
            {'action': 'reject', 'note': ''},
        )
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, RequestStatus.RECEIPT_UPLOADED)

    def test_sabab_bilan_rad_etiladi(self):
        self.client.post(
            reverse('panel:payment_action', args=[self.req.pk]),
            {'action': 'reject', 'note': 'Chek topilmadi'},
        )
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, RequestStatus.REJECTED)
        self.assertEqual(self.req.admin_note, 'Chek topilmadi')

    def test_GET_bilan_amal_bajarilmaydi(self):
        """O'zgartiruvchi amal faqat POST. Aks holda havola bosilsa pul harakati takrorlanardi."""
        response = self.client.get(reverse('panel:payment_action', args=[self.req.pk]))
        self.assertEqual(response.status_code, 405)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, RequestStatus.RECEIPT_UPLOADED)

    def test_bepul_kun_berish_tushumga_kirmaydi(self):
        self.client.post(
            reverse('panel:student_grant', args=[self.student.id]),
            {'days': 14, 'note': 'Sovg\'a'},
        )

        period = SubscriptionPeriod.objects.get(subscription__user=self.student)
        self.assertEqual(period.source, PeriodSource.ADMIN_GRANT)
        self.assertIsNone(period.amount_tiyin)

        summary = reports.revenue_between(
            billing_now() - timedelta(days=1), billing_now() + timedelta(days=1)
        )
        self.assertEqual(summary['total_tiyin'], 0)

    def test_haddan_tashqari_kun_rad_etiladi(self):
        self.client.post(
            reverse('panel:student_grant', args=[self.student.id]), {'days': 5000}
        )
        self.assertFalse(SubscriptionPeriod.objects.filter(subscription__user=self.student).exists())


# ══════════════════════════ Xabar yuborish ══════════════════════════


class MessagingTests(TestCase):
    def setUp(self):
        self.plan = make_plan()
        self.staff = make_user('admin4', staff=True)
        self.linked = make_user('ulangan', chat_id='111')
        self.unlinked = make_user('ulanmagan')

    @patch('billing.telegram.is_configured', return_value=True)
    @patch('billing.telegram.send', return_value=True)
    def test_telegrami_yoq_oquvchi_oluvchi_emas(self, mock_send, mock_conf):
        """
        "Yuborildi" deb yozib qo'yish yolg'on hisobot bo'lardi — ular
        umuman ro'yxatga qo'shilmaydi.
        """
        message = messaging.send_now(self.staff, Audience.ALL, "Salom")

        self.assertEqual(message.total, 1)
        self.assertEqual(message.delivered, 1)
        self.assertFalse(message.deliveries.filter(user=self.unlinked).exists())

    @patch('billing.telegram.is_configured', return_value=True)
    @patch('billing.telegram.send', return_value=True)
    def test_bir_odam_ikki_marta_olmaydi(self, mock_send, mock_conf):
        """Yuborish qayta ishga tushsa ham takror ketmasligi kerak."""
        message = messaging.send_now(self.staff, Audience.ALL, "Salom")
        calls_after_first = mock_send.call_count

        messaging.deliver(message)

        self.assertEqual(mock_send.call_count, calls_after_first)

    @patch('billing.telegram.is_configured', return_value=True)
    @patch('billing.telegram.send', return_value=True)
    def test_uzilgan_yuborish_toxtagan_joyidan_davom_etadi(self, mock_send, mock_conf):
        for i in range(5):
            make_user(f'k{i}', chat_id=f'chat{i}')

        message = messaging.create_message(self.staff, Audience.ALL, "Salom")
        self.assertEqual(message.total, 6)

        # Vaqt budjeti 0 — birinchi qatordan keyin darhol to'xtaydi
        messaging.deliver(message, budget_seconds=0)
        self.assertEqual(mock_send.call_count, 0)

        # Budjetsiz chaqiruv qolganini tugatadi
        messaging.deliver(message)
        message.refresh_from_db()
        self.assertEqual(message.delivered, 6)
        self.assertEqual(message.status, MessageStatus.DONE)

    @patch('billing.telegram.is_configured', return_value=True)
    @patch('billing.telegram.send', return_value=False)
    def test_yetkazilmagan_xabar_belgilanadi(self, mock_send, mock_conf):
        message = messaging.send_now(self.staff, Audience.ALL, "Salom")

        self.assertEqual(message.delivered, 0)
        self.assertEqual(message.failed, 1)
        self.assertEqual(message.status, MessageStatus.FAILED)

    @patch('billing.telegram.is_configured', return_value=True)
    def test_bosh_matn_rad_etiladi(self, mock_conf):
        with self.assertRaises(messaging.MessagingError):
            messaging.create_message(self.staff, Audience.ALL, "   ")

    @patch('billing.telegram.is_configured', return_value=True)
    def test_juda_uzun_matn_rad_etiladi(self, mock_conf):
        with self.assertRaises(messaging.MessagingError):
            messaging.create_message(
                self.staff, Audience.ALL, "a" * (messaging.MAX_BODY_LENGTH + 1)
            )

    @patch('billing.telegram.is_configured', return_value=False)
    def test_telegram_sozlanmagan_bolsa_xabar_yaratilmaydi(self, mock_conf):
        with self.assertRaises(messaging.MessagingError):
            messaging.create_message(self.staff, Audience.ALL, "Salom")
        self.assertEqual(PanelMessage.objects.count(), 0)

    @patch('billing.telegram.is_configured', return_value=True)
    @patch('billing.telegram.send', return_value=True)
    def test_faol_obunachilar_auditoriyasi(self, mock_send, mock_conf):
        extend_subscription(self.linked, days=30, source=PeriodSource.ADMIN_GRANT)
        other = make_user('boshqa', chat_id='222')
        extend_subscription(other, days=30, source=PeriodSource.ADMIN_GRANT)
        Subscription.objects.filter(user=other).update(
            current_period_end=billing_now() - timedelta(days=1)
        )

        message = messaging.send_now(self.staff, Audience.ACTIVE, "Salom")
        self.assertEqual(message.total, 1)
        self.assertTrue(message.deliveries.filter(user=self.linked).exists())


# ══════════════════════════ Testlarni nashr qilish ══════════════════════════


class QuizPublishTests(TestCase):
    def setUp(self):
        self.staff = make_user('admin5', staff=True)
        self.client.force_login(self.staff)

        category = Category.objects.create(name='Python', slug='python')
        module = Module.objects.create(category=category, title='Asoslar')
        self.lesson = Lesson.objects.create(module=module, title='Dars 1', theory='Matn')
        self.quiz = Quiz.objects.create(lesson=self.lesson, title='Test 1', is_published=False)

    def test_savolsiz_test_nashr_qilinmaydi(self):
        """O'quvchi bo'sh testni ochsa buni nosozlik deb qabul qiladi."""
        self.client.post(reverse('panel:quiz_publish', args=[self.quiz.pk]), {'publish': '1'})
        self.quiz.refresh_from_db()
        self.assertFalse(self.quiz.is_published)

    def test_savolli_test_nashr_qilinadi(self):
        self.quiz.questions.create(text='2+2?')
        self.client.post(reverse('panel:quiz_publish', args=[self.quiz.pk]), {'publish': '1'})
        self.quiz.refresh_from_db()
        self.assertTrue(self.quiz.is_published)

    def test_nashrdan_olish(self):
        self.quiz.questions.create(text='2+2?')
        self.quiz.is_published = True
        self.quiz.save(update_fields=['is_published'])

        self.client.post(reverse('panel:quiz_publish', args=[self.quiz.pk]), {'publish': '0'})
        self.quiz.refresh_from_db()
        self.assertFalse(self.quiz.is_published)


# ══════════════════════════ Sahifalar ochilishi ══════════════════════════


class PageRenderTests(TestCase):
    """
    Har bir sahifa bo'sh bazada ham ochilishi.

    NEGA: yangi o'rnatilgan tizimda hech qanday to'lov, o'quvchi va dars
    yo'q. Shablonda nolga bo'lish yoki bo'sh ro'yxatga murojaat bo'lsa,
    panel birinchi kunidayoq 500 xato bilan ochilmasdi.
    """

    def setUp(self):
        make_plan()
        self.staff = make_user('admin6', staff=True)
        self.client.force_login(self.staff)

    def test_bosh_bazada_hamma_sahifa_ochiladi(self):
        for name in (
            'dashboard', 'finance', 'periods', 'payments', 'gateways',
            'students', 'content', 'quizzes', 'messages', 'monitor',
        ):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f'panel:{name}')).status_code, 200)

    def test_kuzatish_bolimlari_ochiladi(self):
        for tab in ('logins', 'mentor', 'certificates'):
            with self.subTest(tab=tab):
                response = self.client.get(reverse('panel:monitor'), {'tab': tab})
                self.assertEqual(response.status_code, 200)

    def test_malumot_bilan_ochiladi(self):
        student = make_user('oquvchi9', chat_id='333')
        extend_subscription(
            student,
            months=1,
            source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CASH,
            amount_tiyin=9_900_000,
        )

        for name in ('dashboard', 'finance', 'periods', 'students'):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f'panel:{name}')).status_code, 200)

        response = self.client.get(reverse('panel:student_detail', args=[student.id]))
        self.assertEqual(response.status_code, 200)

    def test_yangi_dars_formasi_ochiladi(self):
        self.assertEqual(self.client.get(reverse('panel:lesson_new')).status_code, 200)
        self.assertEqual(self.client.get(reverse('panel:module_new')).status_code, 200)

    def test_notogri_sahifa_raqami_yiqitmaydi(self):
        response = self.client.get(reverse('panel:students'), {'page': 'abc'})
        self.assertEqual(response.status_code, 200)


class TemplateCommentTests(TestCase):
    """
    Shablon izohlari sahifada MATN bo'lib chiqmasligi.

    NEGA ALOHIDA TEST: Django'da `{# ... #}` faqat BIR QATORLIK. Ko'p
    qatorga yozilsa qolgan qatorlar foydalanuvchiga ko'rinadi. Bu xato
    ilgari ikki marta sodir bo'lgan.
    """

    def setUp(self):
        make_plan()
        self.staff = make_user('admin7', staff=True)
        self.client.force_login(self.staff)

    def test_izoh_belgilari_sahifada_yoq(self):
        for name in ('dashboard', 'finance', 'payments', 'students', 'messages', 'monitor'):
            with self.subTest(page=name):
                content = self.client.get(reverse(f'panel:{name}')).content.decode()
                self.assertNotIn('{#', content)
                self.assertNotIn('#}', content)
                self.assertNotIn('{% comment %}', content)
                self.assertNotIn('DIQQAT:', content)


class ContextProcessorTests(TestCase):
    """Menyu hisoblagichlari faqat kerakli joyda ishlashi."""

    def setUp(self):
        self.staff = make_user('admin8', staff=True)
        self.student = make_user('oquvchi8')

    def test_oquvchi_sahifasida_hisoblagich_ishlamaydi(self):
        from .context import panel_badges

        class FakeRequest:
            path = '/dashboard/'

        req = FakeRequest()
        req.user = self.student
        # `frontend_url` ham bo'sh qaytadi — panel tashqarisida
        # hech qanday so'rov ketmasligi muhim, kalitlar soni emas
        badges = panel_badges(req)
        self.assertEqual(badges['panel_awaiting'], 0)
        self.assertEqual(badges['panel_drafts'], 0)

    def test_panel_tashqarisida_hisoblagich_ishlamaydi(self):
        """Xodim sayt bo'ylab yurganda har sahifada qo'shimcha so'rov ketmasin."""
        from .context import panel_badges

        class FakeRequest:
            path = '/lessons/'

        req = FakeRequest()
        req.user = self.staff
        # `frontend_url` ham bo'sh qaytadi — panel tashqarisida
        # hech qanday so'rov ketmasligi muhim, kalitlar soni emas
        badges = panel_badges(req)
        self.assertEqual(badges['panel_awaiting'], 0)
        self.assertEqual(badges['panel_drafts'], 0)

    def test_panel_ichida_hisoblanadi(self):
        from .context import panel_badges

        Quiz.objects.create(
            lesson=Lesson.objects.create(
                module=Module.objects.create(
                    category=Category.objects.create(name='C', slug='c'), title='M'
                ),
                title='D',
                theory='T',
            ),
            title='Qoralama test',
            is_published=False,
        )

        class FakeRequest:
            path = '/panel/'

        req = FakeRequest()
        req.user = self.staff
        self.assertEqual(panel_badges(req)['panel_drafts'], 1)
