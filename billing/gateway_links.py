"""
To'lov tizimi sahifasiga o'tish havolalari.

Havola HAR DOIM serverda quriladi. Klientda qurilsa o'quvchi summani
o'zgartirib yuborardi — Payme va Click havoladagi summani ko'rsatadi va
o'sha summani yechadi. (Server baribir `CheckPerformTransaction` /
`prepare` da tekshiradi, lekin noto'g'ri summa ko'rsatilgan sahifa
o'quvchini chalg'itardi.)
"""

import base64
from urllib.parse import urlencode

from django.conf import settings

#: Payme to'lov sahifasi. Parametrlar base64 ichida uzatiladi.
PAYME_CHECKOUT = "https://checkout.paycom.uz/"

#: Click to'lov sahifasi
CLICK_CHECKOUT = "https://my.click.uz/services/pay"


class GatewayNotConfigured(Exception):
    pass


def available(request=None) -> list:
    """Sozlangan to'lov tizimlari ro'yxati (shablon uchun)."""
    from .gateways import click as click_gw
    from .gateways import payme as payme_gw

    items = []
    if payme_gw.is_configured():
        items.append({'code': 'PAYME', 'name': 'Payme'})
    if click_gw.is_configured():
        items.append({'code': 'CLICK', 'name': 'Click'})
    return items


def build_url(provider: str, payment_request, request=None) -> str:
    if provider == 'PAYME':
        return _payme_url(payment_request, request)
    if provider == 'CLICK':
        return _click_url(payment_request, request)
    raise GatewayNotConfigured("Noma'lum to'lov tizimi")


def _return_url(request) -> str:
    if request is None:
        return ''
    from django.urls import reverse

    return request.build_absolute_uri(reverse('billing:plans'))


def _payme_url(payment_request, request) -> str:
    """
    Payme checkout: parametrlar `;` bilan ajratilib base64 ga o'raladi.

    Format:
        m=<merchant_id>;ac.<field>=<value>;a=<amount_tiyin>;c=<return_url>

    Summa TIYINDA — bizning `amount_tiyin` bilan bir xil birlikda,
    aylantirish yo'q.
    """
    merchant_id = getattr(settings, 'PAYME_MERCHANT_ID', '')
    if not merchant_id:
        raise GatewayNotConfigured(
            "Payme sozlanmagan. Karta orqali to'lashingiz mumkin."
        )

    field = getattr(settings, 'PAYME_ACCOUNT_FIELD', 'order_id')
    parts = [
        f"m={merchant_id}",
        f"ac.{field}={payment_request.pk}",
        f"a={payment_request.amount_tiyin}",
    ]
    callback = _return_url(request)
    if callback:
        parts.append(f"c={callback}")

    encoded = base64.b64encode(";".join(parts).encode()).decode()
    return f"{PAYME_CHECKOUT}{encoded}"


def _click_url(payment_request, request) -> str:
    """
    Click to'lov sahifasi.

    Summa SO'MDA — Click tiyinni tushunmaydi. Bu Payme dan asosiy farq,
    shuning uchun aylantirish aynan shu yerda, bir joyda bajariladi.
    """
    service_id = getattr(settings, 'CLICK_SERVICE_ID', '')
    merchant_id = getattr(settings, 'CLICK_MERCHANT_ID', '')
    if not service_id or not merchant_id:
        raise GatewayNotConfigured(
            "Click sozlanmagan. Karta orqali to'lashingiz mumkin."
        )

    params = {
        'service_id': service_id,
        'merchant_id': merchant_id,
        'amount': f"{payment_request.amount_tiyin / 100:.2f}",
        'transaction_param': payment_request.pk,
    }
    callback = _return_url(request)
    if callback:
        params['return_url'] = callback

    return f"{CLICK_CHECKOUT}?{urlencode(params)}"
