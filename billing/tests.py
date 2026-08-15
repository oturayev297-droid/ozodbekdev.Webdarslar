"""
Obuna va to'lov tizimi testlari.

Bu testlar dizayn qoidalarini himoya qiladi — ular buzilsa pul yoki
kontent yo'qoladi:
  * summa faqat serverda hisoblanadi
  * bitta to'lov ikki marta obuna uzaytirmaydi (idempotentlik)
  * narx davrga muzlatiladi
  * ADMIN_GRANT tushum hisobotiga kirmaydi
  * karta rekvizitlari faqat CARD_ISSUED holatida ko'rinadi
  * bepul dars ochiq, qolgani yopiq
"""

import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from core.test_utils import approve_all
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Category, Lesson, Module, Quiz

from . import dates, payment_requests
from .models import (
    AdminSetting,
    PaymentMethod,
    PaymentRequest,
    PeriodSource,
    RequestStatus,
    Subscription,
    SubscriptionPeriod,
)
from .services import (
    CARDS_KEY,
    BillingError,
    extend_subscription,
    get_cards,
    get_plan,
    get_state,
    update_cards,
)


class DateMathTests(TestCase):
    """Toshkent kun chegarasi va oy qo'shish."""

    def test_kun_oxiriga_yaxlitlanadi(self):
        """UTC yarim tuni Toshkentda ertalab 5 — muddat kun oxirida tugashi kerak."""
        end = dates.end_of_day(timezone.now())
        local = end.astimezone(dates.TASHKENT)
        self.assertEqual((local.hour, local.minute, local.second), (23, 59, 59))

    def test_qisqa_oy_togri_hisoblanadi(self):
        """31-yanvar + 1 oy = 28/29-fevral, 3-mart EMAS."""
        jan31 = timezone.datetime(2026, 1, 31, 12, 0, tzinfo=dates.TASHKENT)
        result = dates.add_months(jan31, 1)
        local = result.astimezone(dates.TASHKENT)
        self.assertEqual((local.month, local.day), (2, 28))

    def test_kabisa_yili(self):
        jan31 = timezone.datetime(2028, 1, 31, 12, 0, tzinfo=dates.TASHKENT)
        local = dates.add_months(jan31, 1).astimezone(dates.TASHKENT)
        self.assertEqual((local.month, local.day), (2, 29))

    def test_12_oy_keyingi_yilga_otadi(self):
        d = timezone.datetime(2026, 6, 15, 12, 0, tzinfo=dates.TASHKENT)
        local = dates.add_months(d, 12).astimezone(dates.TASHKENT)
        self.assertEqual((local.year, local.month, local.day), (2027, 6, 15))

    def test_qolgan_kun_hisobi(self):
        now = timezone.now()
        self.assertEqual(dates.days_left(dates.end_of_day(now), now), 0)
        self.assertEqual(dates.days_left(dates.add_days(now, 5), now), 5)
        self.assertEqual(dates.days_left(dates.add_days(now, -2), now), -2)

    def test_erta_tolagan_kunlarini_yoqotmaydi(self):
        """Muddat tugamagan bo'lsa uzaytirish ESKI sanadan boshlanadi."""
        now = timezone.now()
        future = dates.add_days(now, 10)
        self.assertEqual(dates.extension_base(future, now), future)
        past = dates.add_days(now, -10)
        self.assertEqual(dates.extension_base(past, now), now)

    def test_pul_formati(self):
        self.assertEqual(dates.format_money(9_900_000), "99 000 so'm")
        self.assertEqual(dates.format_money(0), "0 so'm")
        self.assertEqual(dates.format_money(None), "—")


class BaseBillingTest(TestCase):
    def setUp(self):
        self.plan = get_plan()
        self.plan.price_per_month_tiyin = 10_000_000  # 100 000 so'm
        self.plan.grace_days = 3
        self.plan.pending_hold_days = 5
        self.plan.trial_days = 7
        self.plan.save()

        self.user = User.objects.create_user(
            username='talaba', email='talaba@test.uz', password='JudaKuchliParol9'
        )
        self.admin = User.objects.create_user(
            username='admin', email='admin@test.uz', password='JudaKuchliParol9', is_staff=True
        )
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas


class ExtendSubscriptionTests(BaseBillingTest):
    """Uzaytirish — yagona yo'l."""

    def test_tolov_davr_yaratadi_va_sanani_yangilaydi(self):
        result = extend_subscription(
            self.user, months=1, source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CARD_TRANSFER,
        )
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.current_period_end, result.current_period_end)
        self.assertEqual(sub.periods.count(), 1)

        period = sub.periods.first()
        self.assertEqual(period.months, 1)
        self.assertEqual(period.amount_tiyin, 10_000_000)  # 1 x 100 000
        self.assertEqual(period.source, PeriodSource.PAYMENT)

    def test_summa_serverda_hisoblanadi(self):
        extend_subscription(
            self.user, months=1, source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CASH,
        )
        self.assertEqual(
            SubscriptionPeriod.objects.get().amount_tiyin, 10_000_000
        )

    def test_narx_davrga_muzlatiladi(self):
        """Narx keyin oshsa, o'tgan davr summasi O'ZGARMAYDI."""
        extend_subscription(
            self.user, months=1, source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CASH,
        )
        period = SubscriptionPeriod.objects.get()
        self.assertEqual(period.amount_tiyin, 10_000_000)

        self.plan.price_per_month_tiyin = 20_000_000
        self.plan.save()

        period.refresh_from_db()
        self.assertEqual(period.amount_tiyin, 10_000_000, "Tarix qayta hisoblanmasligi kerak")

    def test_erta_tolash_qolgan_kunlarni_saqlaydi(self):
        """Muddat tugamasdan to'lasa, qolgan kunlar yo'qolmasligi kerak."""
        first = extend_subscription(
            self.user, months=1, source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CASH,
        )

        # BIRINCHI DAVRNI ORQAGA SURAMIZ. Obuna endi faqat oylik, ya'ni
        # ikkala to'lov ham 1 oy — ular ketma-ket kelsa "ikki marta
        # bosish" himoyasiga tushadi va bu TO'G'RI. Haqiqatda esa ikkinchi
        # to'lov keyinroq keladi, shuni taqlid qilamiz.
        SubscriptionPeriod.objects.filter(pk=first.period.pk).update(
            created_at=dates.now() - timedelta(minutes=5)
        )

        second = extend_subscription(
            self.user, months=1, source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CARD_TRANSFER,
        )
        # Ikkinchi davr birinchisining tugash sanasidan boshlanadi
        self.assertEqual(second.period.start_date, first.current_period_end)
        self.assertGreater(second.current_period_end, first.current_period_end)

    def test_admin_grant_tushumga_kirmaydi(self):
        extend_subscription(
            self.user, days=30, source=PeriodSource.ADMIN_GRANT, admin=self.admin
        )
        period = SubscriptionPeriod.objects.get()
        self.assertFalse(period.is_revenue)
        self.assertIsNone(period.amount_tiyin)
        self.assertIsNone(period.payment_method)
        self.assertIsNone(period.plan)

    def test_notogri_oy_soni_rad_etiladi(self):
        for bad in (2, 5, 7, 24, 0):
            with self.subTest(months=bad):
                with self.assertRaises(BillingError):
                    extend_subscription(
                        self.user, months=bad, source=PeriodSource.PAYMENT,
                        payment_method=PaymentMethod.CASH,
                    )

    def test_tolov_usulisiz_tolov_rad_etiladi(self):
        with self.assertRaises(BillingError):
            extend_subscription(self.user, months=1, source=PeriodSource.PAYMENT)

    def test_ikki_marta_bosish_bloklanadi(self):
        extend_subscription(
            self.user, months=1, source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CASH,
        )
        with self.assertRaises(BillingError) as ctx:
            extend_subscription(
                self.user, months=1, source=PeriodSource.PAYMENT,
                payment_method=PaymentMethod.CASH,
            )
        self.assertEqual(ctx.exception.status, 409)

    def test_har_xil_kun_soni_takror_deb_hisoblanmaydi(self):
        """1 kun bergandan keyin darhol 7 kun berish mumkin bo'lishi kerak."""
        extend_subscription(self.user, days=1, source=PeriodSource.ADMIN_GRANT)
        extend_subscription(self.user, days=7, source=PeriodSource.ADMIN_GRANT)
        self.assertEqual(SubscriptionPeriod.objects.count(), 2)

    def test_uzaytirish_kutish_va_eslatmani_tozalaydi(self):
        sub = Subscription.objects.create(user=self.user, plan=self.plan)
        sub.hold_used_at = timezone.now()
        sub.last_reminder_days_left = 3
        sub.save()

        extend_subscription(
            self.user, months=1, source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CASH,
        )
        sub.refresh_from_db()
        self.assertIsNone(sub.hold_used_at)
        self.assertIsNone(sub.last_reminder_days_left)


class DatabaseConstraintTests(BaseBillingTest):
    """Baza darajasidagi kafolatlar — ilova mantiqidan mustaqil."""

    def test_tolov_usuli_faqat_payment_uchun(self):
        sub = Subscription.objects.create(user=self.user, plan=self.plan)
        now = timezone.now()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SubscriptionPeriod.objects.create(
                    subscription=sub, start_date=now, end_date=now + timedelta(days=1),
                    source=PeriodSource.ADMIN_GRANT,
                    payment_method=PaymentMethod.CASH,  # bepul davrga usul yozib bo'lmaydi
                )

    def test_payment_usulsiz_yozilmaydi(self):
        sub = Subscription.objects.create(user=self.user, plan=self.plan)
        now = timezone.now()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SubscriptionPeriod.objects.create(
                    subscription=sub, start_date=now, end_date=now + timedelta(days=1),
                    source=PeriodSource.PAYMENT, payment_method=None,
                )

    def test_bitta_ochiq_sorov(self):
        payment_requests.create_request(self.user, 1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PaymentRequest.objects.create(
                    user=self.user, plan=self.plan, months=1, amount_tiyin=1,
                    expires_at=timezone.now() + timedelta(days=1),
                )

    def test_bir_tolov_sorovi_bitta_davr(self):
        """IDEMPOTENTLIK: `payment_request` unique."""
        req = payment_requests.create_request(self.user, 1)
        payment_requests.confirm_request(req.pk, self.admin)

        sub = Subscription.objects.get(user=self.user)
        now = timezone.now()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SubscriptionPeriod.objects.create(
                    subscription=sub, start_date=now, end_date=now + timedelta(days=1),
                    source=PeriodSource.PAYMENT, payment_method=PaymentMethod.CASH,
                    payment_request=req,
                )

    def test_naqd_davrlar_yonma_yon_turadi(self):
        """`payment_request=None` bo'lgan bir necha davr bemalol bo'ladi."""
        extend_subscription(self.user, months=1, source=PeriodSource.PAYMENT,
                            payment_method=PaymentMethod.CASH)

        # Ikki marta bosish himoyasidan chetlab o'tamiz — bu yerda
        # tekshirilayotgan narsa boshqa: naqd to'lovlarda
        # `payment_request` bo'sh bo'lgani uchun unique indeks ularni
        # to'smasligi kerak.
        SubscriptionPeriod.objects.all().update(
            created_at=dates.now() - timedelta(minutes=5)
        )

        extend_subscription(self.user, months=1, source=PeriodSource.PAYMENT,
                            payment_method=PaymentMethod.CASH)
        self.assertEqual(SubscriptionPeriod.objects.filter(payment_request=None).count(), 2)


class PaymentRequestFlowTests(BaseBillingTest):
    """To'liq oqim: so'rov -> karta -> chek -> tasdiq."""

    def test_toliq_oqim(self):
        req = payment_requests.create_request(self.user, 1)
        self.assertEqual(req.status, RequestStatus.REQUESTED)
        self.assertEqual(req.amount_tiyin, 10_000_000)

        payment_requests.issue_card(req.pk, self.admin)
        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.CARD_ISSUED)

        payment_requests.mark_receipt_sent(self.user, 'TELEGRAM')
        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.RECEIPT_UPLOADED)
        self.assertIsNotNone(Subscription.objects.get(user=self.user).hold_used_at)

        result = payment_requests.confirm_request(req.pk, self.admin)
        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.CONFIRMED)
        self.assertEqual(req.period.amount_tiyin, 10_000_000)
        self.assertTrue(get_state(self.user).active)

    def test_klient_summani_ozgartira_olmaydi(self):
        """So'rov summasi FAQAT tarifdan hisoblanadi."""
        req = payment_requests.create_request(self.user, 1)
        self.assertEqual(req.amount_tiyin, self.plan.price_for(1))

    def test_ikkinchi_sorov_rad_etiladi(self):
        payment_requests.create_request(self.user, 1)
        with self.assertRaises(BillingError) as ctx:
            payment_requests.create_request(self.user, 1)
        self.assertEqual(ctx.exception.status, 409)

    def test_ikki_marta_tasdiqlash_obunani_ikki_marta_uzaytirmaydi(self):
        req = payment_requests.create_request(self.user, 1)
        payment_requests.confirm_request(req.pk, self.admin)
        end_after_first = Subscription.objects.get(user=self.user).current_period_end

        with self.assertRaises(BillingError) as ctx:
            payment_requests.confirm_request(req.pk, self.admin)
        self.assertEqual(ctx.exception.status, 409)

        self.assertEqual(
            Subscription.objects.get(user=self.user).current_period_end, end_after_first
        )
        self.assertEqual(SubscriptionPeriod.objects.count(), 1)

    def test_rad_etish_sababsiz_bolmaydi(self):
        req = payment_requests.create_request(self.user, 1)
        with self.assertRaises(BillingError):
            payment_requests.reject_request(req.pk, self.admin, "   ")

    def test_rad_etilgan_sorovdan_keyin_yangisi_mumkin(self):
        req = payment_requests.create_request(self.user, 1)
        payment_requests.reject_request(req.pk, self.admin, "Chek kelmadi")
        again = payment_requests.create_request(self.user, 1)
        self.assertEqual(again.status, RequestStatus.REQUESTED)

    def test_karta_faqat_card_issued_holatida_korinadi(self):
        update_cards([{'number': '8600 1111 2222 3333', 'holder': 'TEST'}], self.admin)
        req = payment_requests.create_request(self.user, 1)

        # REQUESTED holatida karta berilmaydi
        with self.assertRaises(BillingError) as ctx:
            payment_requests.get_card_for_user(self.user)
        self.assertEqual(ctx.exception.status, 403)

        payment_requests.issue_card(req.pk, self.admin)
        data = payment_requests.get_card_for_user(self.user)
        self.assertEqual(len(data['cards']), 1)
        self.assertEqual(data['cards'][0]['number'], '8600 1111 2222 3333')

    def test_kartani_faqat_yangi_sorovga_berish_mumkin(self):
        req = payment_requests.create_request(self.user, 1)
        payment_requests.issue_card(req.pk, self.admin)
        with self.assertRaises(BillingError) as ctx:
            payment_requests.issue_card(req.pk, self.admin)
        self.assertEqual(ctx.exception.status, 409)

    def test_javobsiz_sorov_kuyadi(self):
        req = payment_requests.create_request(self.user, 1)
        PaymentRequest.objects.filter(pk=req.pk).update(
            expires_at=timezone.now() - timedelta(days=1)
        )
        self.assertEqual(payment_requests.expire_stale_requests(), 1)
        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.EXPIRED)

    def test_chek_yuborilgan_sorov_hech_qachon_kuymaydi(self):
        """Pul yuborilib tasdiq kutilayotganda so'rov yo'qolmasligi kerak."""
        req = payment_requests.create_request(self.user, 1)
        payment_requests.mark_receipt_sent(self.user)
        PaymentRequest.objects.filter(pk=req.pk).update(
            expires_at=timezone.now() - timedelta(days=30)
        )
        self.assertEqual(payment_requests.expire_stale_requests(), 0)
        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.RECEIPT_UPLOADED)


class StatusTests(BaseBillingTest):
    """Holat bayroqdan emas, sanadan HISOBLANADI."""

    def test_obuna_yoq(self):
        state = get_state(self.user)
        self.assertEqual(state.status, 'NONE')
        self.assertFalse(state.active)

    def test_faol(self):
        extend_subscription(self.user, months=1, source=PeriodSource.PAYMENT,
                            payment_method=PaymentMethod.CASH)
        state = get_state(self.user)
        self.assertEqual(state.status, 'ACTIVE')
        self.assertTrue(state.active)

    def test_sinov_muddati(self):
        extend_subscription(self.user, days=7, source=PeriodSource.TRIAL)
        self.assertEqual(get_state(self.user).status, 'TRIAL')

    def test_muhlat_ichida_faol_qoladi(self):
        extend_subscription(self.user, months=1, source=PeriodSource.PAYMENT,
                            payment_method=PaymentMethod.CASH)
        sub = Subscription.objects.get(user=self.user)
        # Muddat 1 kun oldin tugagan, muhlat 3 kun
        sub.current_period_end = dates.add_days(timezone.now(), -1)
        sub.save()

        state = get_state(self.user)
        self.assertEqual(state.status, 'GRACE')
        self.assertTrue(state.active, "Muhlat ichida kirish ochiq qolishi kerak")

    def test_muhlat_tugasa_yopiladi(self):
        extend_subscription(self.user, months=1, source=PeriodSource.PAYMENT,
                            payment_method=PaymentMethod.CASH)
        sub = Subscription.objects.get(user=self.user)
        sub.current_period_end = dates.add_days(timezone.now(), -10)
        sub.save()

        state = get_state(self.user)
        self.assertEqual(state.status, 'EXPIRED')
        self.assertFalse(state.active)

    def test_kutish_rejimi_qulflashni_toxtatadi(self):
        req = payment_requests.create_request(self.user, 1)
        payment_requests.mark_receipt_sent(self.user)

        sub = Subscription.objects.get(user=self.user)
        sub.current_period_end = dates.add_days(timezone.now(), -10)  # muhlat ham tugagan
        sub.save()

        state = get_state(self.user)
        self.assertEqual(state.status, 'HOLD')
        self.assertTrue(state.active, "Chek yuborilgan odam qulflanmasligi kerak")

    def test_rad_etilsa_kutish_darhol_tugaydi(self):
        req = payment_requests.create_request(self.user, 1)
        payment_requests.mark_receipt_sent(self.user)

        sub = Subscription.objects.get(user=self.user)
        sub.current_period_end = dates.add_days(timezone.now(), -10)
        sub.save()
        self.assertTrue(get_state(self.user).active)

        payment_requests.reject_request(req.pk, self.admin, "Chek yolg'on")
        self.assertFalse(get_state(self.user).active, "Rad etilgach darhol yopilishi kerak")

    def test_kutish_bir_davrda_bir_marta(self):
        """Qayta-qayta "to'ladim" deb cheksiz uzaytirib bo'lmaydi."""
        req = payment_requests.create_request(self.user, 1)
        payment_requests.mark_receipt_sent(self.user)
        first_hold = Subscription.objects.get(user=self.user).hold_used_at

        payment_requests.reject_request(req.pk, self.admin, "Xato")
        payment_requests.create_request(self.user, 1)
        payment_requests.mark_receipt_sent(self.user)

        self.assertEqual(
            Subscription.objects.get(user=self.user).hold_used_at, first_hold,
            "hold_used_at faqat yangi DAVR ochilganda tozalanadi",
        )

    def test_admin_cheklanmaydi(self):
        self.assertTrue(get_state(self.admin).active)


class CardStorageTests(BaseBillingTest):
    def test_kartalar_saqlanadi_va_tozalanadi(self):
        update_cards([
            {'number': '  8600 1111 2222 3333  ', 'holder': 'test', 'bank': 'Uzcard'},
            {'number': '', 'holder': 'nomerisiz'},  # tashlab ketiladi
            'satr emas',                              # tashlab ketiladi
        ], self.admin)
        cards = get_cards()
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['number'], '8600 1111 2222 3333')

    def test_buzilgan_json_bosh_royxat_qaytaradi(self):
        AdminSetting.objects.update_or_create(key=CARDS_KEY, defaults={'value': '{buzilgan'})
        self.assertEqual(get_cards(), [])

    def test_kop_karta_cheklovi(self):
        with self.assertRaises(BillingError):
            update_cards([{'number': str(i)} for i in range(11)], self.admin)


class ContentGatingTests(BaseBillingTest):
    """Bepul dars ochiq, qolgani obunada."""

    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name="Python", slug="python")
        self.module = Module.objects.create(category=self.category, title="Asoslar", order=1)
        self.free_lesson = Lesson.objects.create(
            module=self.module, title="Bepul kirish", theory="Matn", order=1, is_free=True
        )
        self.paid_lesson = Lesson.objects.create(
            module=self.module, title="Pullik dars", theory="Maxfiy matn", order=2, is_free=False
        )
        self.paid_quiz = Quiz.objects.create(lesson=self.paid_lesson, title="Pullik test")
        self.client.force_login(self.user)
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def test_yangi_dars_yopiq_tugiladi(self):
        """FAIL CLOSED: bayroqni unutish kontentni bepul qilmasligi kerak."""
        lesson = Lesson.objects.create(module=self.module, title="Yangi", order=3)
        self.assertFalse(lesson.is_free)

    def test_bepul_dars_videosi_ochiq(self):
        response = self.client.get(reverse('lesson_video', args=[self.free_lesson.id]))
        # Video fayli yo'q -> 404, lekin 402 (paywall) EMAS
        self.assertEqual(response.status_code, 404)

    def test_pullik_dars_videosi_yopiq(self):
        response = self.client.get(reverse('lesson_video', args=[self.paid_lesson.id]))
        self.assertEqual(response.status_code, 402)

    def test_obuna_bilan_pullik_video_ochiladi(self):
        extend_subscription(self.user, months=1, source=PeriodSource.PAYMENT,
                            payment_method=PaymentMethod.CASH)
        response = self.client.get(reverse('lesson_video', args=[self.paid_lesson.id]))
        self.assertEqual(response.status_code, 404, "Paywall emas, faqat video yo'q")

    def test_qulflangan_dars_mazmuni_json_ga_tushmaydi(self):
        """CSS bilan yashirish yetarli emas — mazmun serverdan kelmasligi kerak."""
        response = self.client.get(reverse('lessons'))
        self.assertNotContains(response, "Maxfiy matn")

        data = json.loads(response.context['course_data_json'])
        lessons = {l['title']: l for l in data['python']['lessons']}
        self.assertFalse(lessons['Pullik dars']['unlocked'])
        self.assertEqual(lessons['Pullik dars']['theoryHtml'], '')
        self.assertEqual(lessons['Pullik dars']['videoUrl'], '')
        # Rasmlar ham yuborilmaydi: dars mazmuni rasmda bo'lsa,
        # ularni qoldirish qulfni ma'nosiz qilardi
        self.assertEqual(lessons['Pullik dars']['images'], [])
        self.assertTrue(lessons['Bepul kirish']['unlocked'])
        self.assertIn('Matn', lessons['Bepul kirish']['theoryHtml'])

    def test_obuna_bilan_mazmun_keladi(self):
        extend_subscription(self.user, months=1, source=PeriodSource.PAYMENT,
                            payment_method=PaymentMethod.CASH)
        data = json.loads(self.client.get(reverse('lessons')).context['course_data_json'])
        lessons = {l['title']: l for l in data['python']['lessons']}
        self.assertTrue(lessons['Pullik dars']['unlocked'])
        # Matn endi serverda HTML ga aylantiriladi, shuning uchun
        # aynan tenglik emas, ichida borligi tekshiriladi
        self.assertIn('Maxfiy matn', lessons['Pullik dars']['theoryHtml'])

    def test_pullik_test_yopiq(self):
        response = self.client.get(reverse('quiz_detail', args=[self.paid_quiz.id]))
        self.assertEqual(response.status_code, 402)

    def test_pullik_testni_topshirib_bolmaydi(self):
        response = self.client.post(
            reverse('submit_quiz', args=[self.paid_quiz.id]),
            data=json.dumps({'answers': {}}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 402)

    def test_test_darsdan_huquqni_meros_oladi(self):
        self.paid_lesson.is_free = True
        self.paid_lesson.save()
        response = self.client.get(reverse('quiz_detail', args=[self.paid_quiz.id]))
        self.assertEqual(response.status_code, 200)

    def test_qulflangan_darsni_tugatib_bolmaydi(self):
        response = self.client.post(reverse('complete_lesson', args=[self.paid_lesson.id]))
        self.assertEqual(response.status_code, 402)
        self.assertEqual(self.user.progress.count(), 0)

    def test_bepul_darsni_tugatish_mumkin(self):
        response = self.client.post(reverse('complete_lesson', args=[self.free_lesson.id]))
        self.assertEqual(response.status_code, 200)


class BillingViewTests(BaseBillingTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def test_tarif_sahifasi_narxlarni_korsatadi(self):
        response = self.client.get(reverse('billing:plans'))
        self.assertEqual(response.status_code, 200)
        options = response.context['options']
        # Obuna FAQAT OYLIK — uzoq muddatli variantlar olib tashlangan
        self.assertEqual([o['months'] for o in options], [1])
        self.assertEqual(options[0]['amount_display'], "100 000 so'm")

    def test_sorov_yuborish(self):
        response = self.client.post(reverse('billing:create_request'), {'months': 1})
        self.assertEqual(response.status_code, 302)
        req = PaymentRequest.objects.get(user=self.user)
        self.assertEqual(req.months, 1)
        self.assertEqual(req.amount_tiyin, 10_000_000)

    def test_endi_ruxsat_etilmagan_muddat_rad_etiladi(self):
        """3 oylik obuna olib tashlangan — so'rov yaratilmasligi kerak."""
        self.client.post(reverse('billing:create_request'), {'months': 3})
        self.assertEqual(PaymentRequest.objects.count(), 0)

    def test_notogri_muddat_rad_etiladi(self):
        self.client.post(reverse('billing:create_request'), {'months': 7})
        self.assertEqual(PaymentRequest.objects.count(), 0)

    def test_karta_sahifada_faqat_berilgandan_keyin_korinadi(self):
        update_cards([{'number': '8600 9999 8888 7777', 'holder': 'TEST'}], self.admin)
        req = payment_requests.create_request(self.user, 1)

        response = self.client.get(reverse('billing:plans'))
        self.assertNotContains(response, '8600 9999 8888 7777')

        payment_requests.issue_card(req.pk, self.admin)
        response = self.client.get(reverse('billing:plans'))
        self.assertContains(response, '8600 9999 8888 7777')

    def test_login_talab_qiladi(self):
        self.client.logout()
        for name in ('billing:plans', 'billing:history'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login/', response['Location'])

    def test_chek_yuborilgan_sorovni_bekor_qilib_bolmaydi(self):
        payment_requests.create_request(self.user, 1)
        payment_requests.mark_receipt_sent(self.user)
        self.client.post(reverse('billing:cancel_request'))
        self.assertEqual(
            PaymentRequest.objects.get(user=self.user).status,
            RequestStatus.RECEIPT_UPLOADED,
        )

    def test_tarix_sahifasi(self):
        extend_subscription(self.user, months=1, source=PeriodSource.PAYMENT,
                            payment_method=PaymentMethod.CASH)
        response = self.client.get(reverse('billing:history'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['periods']), 1)
