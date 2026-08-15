"""
Payme va Click integratsiyasi testlari.

Bu testlar PUL bilan bog'liq qoidalarni himoya qiladi:
  * summa faqat serverdagi qiymat bilan solishtiriladi;
  * imzo / autentifikatsiya tekshirilmasa hech narsa bajarilmaydi;
  * takror so'rov obunani ikki marta uzaytirmaydi;
  * Payme TIYINDA, Click SO'MDA — birliklar aralashmaydi.
"""

import base64
import hashlib
import json
import time

from django.contrib.auth.models import User
from core.test_utils import approve_all
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Category, Lesson, Module

from . import payment_requests
from .gateways import click as click_gw
from .gateways import payme as payme_gw
from .models import (
    GatewayTransaction,
    PaymentMethod,
    PaymentRequest,
    PeriodSource,
    RequestStatus,
    Subscription,
    SubscriptionPeriod,
)
from .services import get_plan, get_state

PAYME_KEY = "test-payme-kaliti-123"
CLICK_SECRET = "test-click-siri-456"
CLICK_SERVICE_ID = "11111"


@override_settings(
    PAYME_MERCHANT_ID="merchant-1",
    PAYME_KEY=PAYME_KEY,
    PAYME_ACCOUNT_FIELD="order_id",
    CLICK_SERVICE_ID=CLICK_SERVICE_ID,
    CLICK_MERCHANT_ID="22222",
    CLICK_SECRET_KEY=CLICK_SECRET,
)
class GatewayBase(TestCase):
    def setUp(self):
        self.plan = get_plan()
        self.plan.price_per_month_tiyin = 10_000_000  # 100 000 so'm
        self.plan.save()

        self.user = User.objects.create_user(
            username='talaba', email='t@test.uz', password='Parol12345678'
        )
        self.request = payment_requests.create_request(self.user, 1)
        # 3 oy x 100 000 = 300 000 so'm = 30 000 000 tiyin
        self.assertEqual(self.request.amount_tiyin, 10_000_000)
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas


# ==========================================================================
# Payme
# ==========================================================================


class PaymeAuthTests(GatewayBase):
    def _header(self, login="Paycom", key=PAYME_KEY):
        raw = base64.b64encode(f"{login}:{key}".encode()).decode()
        return f"Basic {raw}"

    def test_togri_kalit(self):
        self.assertTrue(payme_gw.check_auth(self._header()))

    def test_notogri_kalit(self):
        self.assertFalse(payme_gw.check_auth(self._header(key="boshqa")))

    def test_notogri_login(self):
        self.assertFalse(payme_gw.check_auth(self._header(login="admin")))

    def test_bosh_sarlavha(self):
        self.assertFalse(payme_gw.check_auth(""))
        self.assertFalse(payme_gw.check_auth("Bearer abc"))

    def test_buzilgan_base64(self):
        """Buzilgan sarlavha 500 EMAS, jimgina rad etilishi kerak."""
        self.assertFalse(payme_gw.check_auth("Basic !!!buzilgan!!!"))

    def test_ascii_bolmagan_kalit_yiqitmaydi(self):
        """
        `secrets.compare_digest` satrlarda faqat ASCII ni qabul qiladi.
        ASCII bo'lmagan qiymat yuborilsa server yiqilmasligi kerak.
        """
        raw = base64.b64encode("Paycom:parol-ўзбекча".encode()).decode()
        self.assertFalse(payme_gw.check_auth(f"Basic {raw}"))

    def test_endpoint_ruxsatsiz_sorovni_rad_etadi(self):
        response = self.client.post(
            reverse('billing:payme_endpoint'),
            data=json.dumps({'method': 'CheckPerformTransaction', 'params': {}, 'id': 1}),
            content_type='application/json',
        )
        # Har doim 200, xato javob TANASIDA
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['error']['code'], payme_gw.ERR_UNAUTHORIZED)


class PaymeMethodTests(GatewayBase):
    def _call(self, method, params, key=PAYME_KEY, request_id=1):
        auth = base64.b64encode(f"Paycom:{key}".encode()).decode()
        response = self.client.post(
            reverse('billing:payme_endpoint'),
            data=json.dumps({'method': method, 'params': params, 'id': request_id}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f"Basic {auth}",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _account(self):
        return {'order_id': str(self.request.pk)}

    # ── CheckPerformTransaction ──

    def test_check_perform_ruxsat_beradi(self):
        data = self._call('CheckPerformTransaction', {
            'amount': 10_000_000, 'account': self._account(),
        })
        self.assertTrue(data['result']['allow'])

    def test_notogri_summa_rad_etiladi(self):
        data = self._call('CheckPerformTransaction', {
            'amount': 100, 'account': self._account(),
        })
        self.assertEqual(data['error']['code'], payme_gw.ERR_INVALID_AMOUNT)

    def test_mavjud_bolmagan_sorov(self):
        data = self._call('CheckPerformTransaction', {
            'amount': 10_000_000, 'account': {'order_id': '999999'},
        })
        # -31050 oralig'i: Payme buni "foydalanuvchi xatosi" deb ko'rsatadi
        self.assertEqual(data['error']['code'], payme_gw.ERR_ACCOUNT)

    def test_account_bosh(self):
        data = self._call('CheckPerformTransaction', {'amount': 10_000_000, 'account': {}})
        self.assertEqual(data['error']['code'], payme_gw.ERR_ACCOUNT)

    def test_xato_xabari_uch_tilda(self):
        data = self._call('CheckPerformTransaction', {
            'amount': 10_000_000, 'account': {'order_id': '999999'},
        })
        self.assertEqual(set(data['error']['message']), {'uz', 'ru', 'en'})

    def test_notanish_metod(self):
        data = self._call('YoqBundayMetod', {})
        self.assertEqual(data['error']['code'], payme_gw.ERR_METHOD_NOT_FOUND)

    # ── CreateTransaction ──

    def test_create_transaction(self):
        data = self._call('CreateTransaction', {
            'id': 'tx-1', 'time': int(time.time() * 1000),
            'amount': 10_000_000, 'account': self._account(),
        })
        result = data['result']
        self.assertEqual(result['state'], GatewayTransaction.State.CREATED)
        self.assertEqual(GatewayTransaction.objects.count(), 1)

    def test_create_takrorlanishga_chidamli(self):
        """Payme tarmoq uzilganda so'rovni ATAYLAB qayta yuboradi."""
        params = {
            'id': 'tx-1', 'time': int(time.time() * 1000),
            'amount': 10_000_000, 'account': self._account(),
        }
        first = self._call('CreateTransaction', params)['result']
        second = self._call('CreateTransaction', params)['result']

        self.assertEqual(first['transaction'], second['transaction'])
        self.assertEqual(GatewayTransaction.objects.count(), 1)

    def test_create_notogri_summa(self):
        data = self._call('CreateTransaction', {
            'id': 'tx-1', 'time': int(time.time() * 1000),
            'amount': 1, 'account': self._account(),
        })
        self.assertEqual(data['error']['code'], payme_gw.ERR_INVALID_AMOUNT)
        self.assertEqual(GatewayTransaction.objects.count(), 0)

    def test_ikkinchi_ochiq_tranzaksiya_rad_etiladi(self):
        """Bitta so'rovga ikki marta to'lab bo'lmasin."""
        self._call('CreateTransaction', {
            'id': 'tx-1', 'time': int(time.time() * 1000),
            'amount': 10_000_000, 'account': self._account(),
        })
        data = self._call('CreateTransaction', {
            'id': 'tx-2', 'time': int(time.time() * 1000),
            'amount': 10_000_000, 'account': self._account(),
        })
        self.assertEqual(data['error']['code'], payme_gw.ERR_CANNOT_PERFORM)

    # ── PerformTransaction ──

    def _create(self, external_id='tx-1'):
        return self._call('CreateTransaction', {
            'id': external_id, 'time': int(time.time() * 1000),
            'amount': 10_000_000, 'account': self._account(),
        })

    def test_perform_obunani_uzaytiradi(self):
        self._create()
        data = self._call('PerformTransaction', {'id': 'tx-1'})

        self.assertEqual(data['result']['state'], GatewayTransaction.State.PERFORMED)
        self.assertTrue(get_state(self.user).active)

        self.request.refresh_from_db()
        self.assertEqual(self.request.status, RequestStatus.CONFIRMED)

        period = SubscriptionPeriod.objects.get()
        self.assertEqual(period.source, PeriodSource.PAYMENT)
        self.assertEqual(period.payment_method, PaymentMethod.PAYME)
        self.assertEqual(period.amount_tiyin, 10_000_000)
        self.assertEqual(period.months, 1)

    def test_perform_takrorlanishga_chidamli(self):
        """IDEMPOTENTLIK: takror so'rov obunani ikki marta uzaytirmasin."""
        self._create()
        first = self._call('PerformTransaction', {'id': 'tx-1'})['result']
        end_after_first = Subscription.objects.get(user=self.user).current_period_end

        second = self._call('PerformTransaction', {'id': 'tx-1'})['result']

        self.assertEqual(first['perform_time'], second['perform_time'])
        self.assertEqual(SubscriptionPeriod.objects.count(), 1)
        self.assertEqual(
            Subscription.objects.get(user=self.user).current_period_end, end_after_first
        )

    def test_perform_mavjud_bolmagan_tranzaksiya(self):
        data = self._call('PerformTransaction', {'id': 'yoq'})
        self.assertEqual(data['error']['code'], payme_gw.ERR_TRANSACTION_NOT_FOUND)

    def test_bekor_qilingandan_keyin_perform_bolmaydi(self):
        self._create()
        self._call('CancelTransaction', {'id': 'tx-1', 'reason': 1})
        data = self._call('PerformTransaction', {'id': 'tx-1'})
        self.assertEqual(data['error']['code'], payme_gw.ERR_CANNOT_PERFORM)

    # ── CancelTransaction ──

    def test_cancel_tolovdan_oldin(self):
        self._create()
        data = self._call('CancelTransaction', {'id': 'tx-1', 'reason': 1})
        self.assertEqual(data['result']['state'], GatewayTransaction.State.CANCELLED)

    def test_cancel_tolovdan_keyin_jurnalni_ochirmaydi(self):
        """
        Davr jurnali moliyaviy yozuv — bekor qilish uni O'CHIRMAYDI.
        Admin xabardor qilinadi va qarorni u qabul qiladi.
        """
        self._create()
        self._call('PerformTransaction', {'id': 'tx-1'})
        self.assertEqual(SubscriptionPeriod.objects.count(), 1)

        data = self._call('CancelTransaction', {'id': 'tx-1', 'reason': 5})
        self.assertEqual(
            data['result']['state'], GatewayTransaction.State.CANCELLED_AFTER_PERFORM
        )
        self.assertEqual(SubscriptionPeriod.objects.count(), 1, "Jurnal o'chirilmasligi kerak")

    # ── CheckTransaction / GetStatement ──

    def test_check_transaction(self):
        self._create()
        data = self._call('CheckTransaction', {'id': 'tx-1'})['result']
        self.assertEqual(data['state'], GatewayTransaction.State.CREATED)
        self.assertEqual(data['perform_time'], 0)
        self.assertEqual(data['cancel_time'], 0)

    def test_get_statement(self):
        self._create()
        now = int(time.time() * 1000)
        data = self._call('GetStatement', {'from': now - 60000, 'to': now + 60000})['result']
        self.assertEqual(len(data['transactions']), 1)
        self.assertEqual(data['transactions'][0]['id'], 'tx-1')
        self.assertEqual(data['transactions'][0]['amount'], 10_000_000)


# ==========================================================================
# Click
# ==========================================================================


class ClickSignTests(GatewayBase):
    def test_imzo_formulasi(self):
        """Rasmiy click-integration-php kutubxonasidagi formula."""
        data = {
            'click_trans_id': '123', 'service_id': CLICK_SERVICE_ID,
            'merchant_trans_id': '7', 'amount': '100000.00',
            'action': '0', 'sign_time': '2026-08-14 12:00:00',
        }
        expected = hashlib.md5(
            ('123' + CLICK_SERVICE_ID + CLICK_SECRET + '7' + '' +
             '100000.00' + '0' + '2026-08-14 12:00:00').encode()
        ).hexdigest()
        self.assertEqual(click_gw.build_sign(data), expected)

    def test_complete_imzosida_prepare_id_bor(self):
        data = {
            'click_trans_id': '123', 'service_id': CLICK_SERVICE_ID,
            'merchant_trans_id': '7', 'merchant_prepare_id': '42',
            'amount': '100000.00', 'action': '1', 'sign_time': '2026-08-14 12:00:00',
        }
        expected = hashlib.md5(
            ('123' + CLICK_SERVICE_ID + CLICK_SECRET + '7' + '42' +
             '100000.00' + '1' + '2026-08-14 12:00:00').encode()
        ).hexdigest()
        self.assertEqual(click_gw.build_sign(data), expected)


class ClickFlowTests(GatewayBase):
    def _payload(self, action, **extra):
        data = {
            'click_trans_id': '900001',
            'service_id': CLICK_SERVICE_ID,
            'click_paydoc_id': '555',
            'merchant_trans_id': str(self.request.pk),
            # Click SO'MDA yuboradi — 30 000 000 tiyin = 300 000 so'm
            'amount': '100000.00',
            'action': str(action),
            'error': '0',
            'error_note': 'Success',
            'sign_time': '2026-08-14 12:00:00',
        }
        data.update(extra)
        data['sign_string'] = click_gw.build_sign(data)
        return data

    def _post(self, name, data):
        response = self.client.post(reverse(f'billing:{name}'), data)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_prepare(self):
        result = self._post('click_prepare', self._payload(0))
        self.assertEqual(result['error'], click_gw.OK)
        self.assertIsNotNone(result['merchant_prepare_id'])
        self.assertEqual(GatewayTransaction.objects.count(), 1)

    def test_notogri_imzo(self):
        data = self._payload(0)
        data['sign_string'] = 'a' * 32
        result = self._post('click_prepare', data)
        self.assertEqual(result['error'], click_gw.ERR_SIGN)
        self.assertEqual(GatewayTransaction.objects.count(), 0)

    def test_maydon_yetishmasa(self):
        data = self._payload(0)
        del data['click_paydoc_id']
        result = self._post('click_prepare', data)
        self.assertEqual(result['error'], click_gw.ERR_BAD_REQUEST)

    def test_notogri_summa(self):
        data = self._payload(0, amount='1000.00')
        result = self._post('click_prepare', data)
        self.assertEqual(result['error'], click_gw.ERR_AMOUNT)

    def test_tiyin_somga_chalkashtirilmaydi(self):
        """
        Click SO'MDA yuboradi. Agar kimdir tiyin qiymatini yuborsa
        (10000000), u 100 barobar katta va RAD ETILISHI kerak.
        """
        data = self._payload(0, amount='10000000.00')
        result = self._post('click_prepare', data)
        self.assertEqual(result['error'], click_gw.ERR_AMOUNT)

    def test_mavjud_bolmagan_sorov(self):
        data = self._payload(0, merchant_trans_id='999999')
        result = self._post('click_prepare', data)
        self.assertEqual(result['error'], click_gw.ERR_USER_NOT_FOUND)

    def test_toliq_oqim(self):
        prepared = self._post('click_prepare', self._payload(0))
        prepare_id = prepared['merchant_prepare_id']

        result = self._post(
            'click_complete', self._payload(1, merchant_prepare_id=str(prepare_id))
        )
        self.assertEqual(result['error'], click_gw.OK)

        self.assertTrue(get_state(self.user).active)
        period = SubscriptionPeriod.objects.get()
        self.assertEqual(period.payment_method, PaymentMethod.CLICK)
        self.assertEqual(period.amount_tiyin, 10_000_000)

    def test_complete_takrorlanishga_chidamli(self):
        prepared = self._post('click_prepare', self._payload(0))
        payload = self._payload(1, merchant_prepare_id=str(prepared['merchant_prepare_id']))

        self._post('click_complete', payload)
        end_after_first = Subscription.objects.get(user=self.user).current_period_end

        second = self._post('click_complete', payload)
        self.assertEqual(second['error'], click_gw.ERR_ALREADY_PAID)

        self.assertEqual(SubscriptionPeriod.objects.count(), 1)
        self.assertEqual(
            Subscription.objects.get(user=self.user).current_period_end, end_after_first
        )

    def test_click_xato_yuborsa_obuna_ochilmaydi(self):
        """`error < 0` — pul yechilmagan. Obuna ochilib ketmasligi kerak."""
        prepared = self._post('click_prepare', self._payload(0))
        payload = self._payload(
            1, merchant_prepare_id=str(prepared['merchant_prepare_id']), error='-5'
        )
        result = self._post('click_complete', payload)

        self.assertEqual(result['error'], click_gw.ERR_CANCELLED)
        self.assertFalse(get_state(self.user).active)
        self.assertEqual(SubscriptionPeriod.objects.count(), 0)

    def test_prepare_siz_complete_bolmaydi(self):
        payload = self._payload(1, merchant_prepare_id='999999')
        result = self._post('click_complete', payload)
        self.assertEqual(result['error'], click_gw.ERR_TX_NOT_FOUND)

    def test_boshqa_service_id_rad_etiladi(self):
        data = self._payload(0, service_id='99999')
        # Imzo boshqa service_id bilan qurilgan, lekin sozlamadagisi boshqa
        result = self._post('click_prepare', data)
        self.assertEqual(result['error'], click_gw.ERR_SIGN)


# ==========================================================================
# Havolalar va sozlanmagan holat
# ==========================================================================


class GatewayLinkTests(GatewayBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        approve_all()   # ruxsat darvozasi bu testlarning mavzusi emas

    def test_payme_havolasi_tiyinda(self):
        from . import gateway_links

        url = gateway_links.build_url('PAYME', self.request)
        encoded = url.rsplit('/', 1)[-1]
        decoded = base64.b64decode(encoded).decode()

        self.assertIn(f"a=10000000", decoded, "Payme summani TIYINDA kutadi")
        self.assertIn(f"ac.order_id={self.request.pk}", decoded)

    def test_click_havolasi_somda(self):
        from . import gateway_links

        url = gateway_links.build_url('CLICK', self.request)
        self.assertIn("amount=100000.00", url, "Click summani SO'MDA kutadi")
        self.assertIn(f"transaction_param={self.request.pk}", url)

    def test_yonaltirish_ishlaydi(self):
        response = self.client.get(
            reverse('billing:start_payment', args=[self.request.pk, 'payme'])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('checkout.paycom.uz', response['Location'])

    def test_begona_sorovga_yonaltirilmaydi(self):
        other = User.objects.create_user(username='boshqa', password='Parol12345678')
        self.client.force_login(other)
        response = self.client.get(
            reverse('billing:start_payment', args=[self.request.pk, 'payme'])
        )
        self.assertEqual(response.status_code, 404)


