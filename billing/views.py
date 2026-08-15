"""
`billing` ko'rinishlari — FAQAT TASHQI XIZMATLAR UCHUN.

O'quvchi ko'radigan sahifalar (tarif, to'lov so'rovi, tarix) olib
tashlandi — ular React frontendda va `/api/v1/subscription/` orqali
ishlaydi.

Bu yerda uchtasi qoldi:

  start_gateway_payment — imzolangan to'lov havolasini quradi va
                          o'quvchini Payme/Click sahifasiga yuboradi.
                          Imzo SERVERDA qurilishi shart.

  telegram_webhook      — Telegram chaqiradi. Maxfiy manzil.

  _error_response       — yuqoridagilar uchun xato javobi.
"""

import json
import logging
import secrets

from django.conf import settings as dj_settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import gateway_links, telegram
from .models import OPEN_STATUSES, PaymentRequest
from .services import BillingError

logger = logging.getLogger(__name__)


@login_required
def start_gateway_payment(request, request_id, provider):
    """
    O'quvchini to'lov tizimi sahifasiga yo'naltiradi.

    Havola SERVERDA quriladi: summa va so'rov raqami shu yerdan olinadi.
    Klientda qurilsa o'quvchi summani o'zgartirib yuborardi — Payme va
    Click esa havoladagi summani ko'rsatadi.
    """
    payment_request = get_object_or_404(
        PaymentRequest, pk=request_id, user=request.user
    )

    if payment_request.status not in OPEN_STATUSES:
        # XATO JSON BILAN QAYTARILADI. Ilgari bu yerda `messages` va
        # tarif sahifasiga yo'naltirish bor edi — sahifa endi yo'q va
        # xabarni ko'rsatadigan joy ham qolmagan.
        return JsonResponse(
            {'success': False, 'error': "Bu to'lov so'rovi yopilgan.",
             'code': 'REQUEST_CLOSED'},
            status=409,
        )

    provider = (provider or '').upper()
    try:
        url = gateway_links.build_url(provider, payment_request, request)
    except gateway_links.GatewayNotConfigured as exc:
        return JsonResponse(
            {'success': False, 'error': str(exc), 'code': 'GATEWAY_NOT_CONFIGURED'},
            status=503,
        )

    logger.info(
        "[TO'LOV] %s -> %s (so'rov #%s)", request.user.username, provider, payment_request.pk
    )
    return redirect(url)


@csrf_exempt
@require_POST
def telegram_webhook(request, secret):
    """
    Telegram dan keladigan yangilanishlar.

    MAXFIY MANZIL: URL ichidagi `secret` `.env` dagi qiymat bilan
    solishtiriladi. Mos kelmasa 404 — endpoint borligi ham bilinmaydi.
    Busiz har kim bot nomidan soxta `/start` yuborib begona hisobni
    o'ziga bog'lab olardi.

    `csrf_exempt` ATAYLAB: so'rov Telegram serveridan keladi, sessiya
    va CSRF tokeni yo'q. Himoya maxfiy manzil va token xeshi orqali.
    """
    expected = getattr(dj_settings, 'TELEGRAM_WEBHOOK_SECRET', '')
    if not expected or not secrets.compare_digest(str(secret), expected):
        raise Http404()

    try:
        update = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': True})  # Telegram qayta yubormasin

    message = update.get('message') or {}
    chat_id = (message.get('chat') or {}).get('id')
    text = (message.get('text') or '').strip()

    if chat_id and text.startswith('/start'):
        parts = text.split(maxsplit=1)
        token = parts[1] if len(parts) > 1 else ''
        user = telegram.consume_link_token(token, chat_id) if token else None

        if user:
            name = getattr(getattr(user, 'profile', None), 'full_name', '') or user.username
            telegram.send(
                chat_id,
                f"✅ <b>Hisob ulandi</b>\n\nSalom, {name}!\n\n"
                f"Endi to'lov rekvizitlari, tasdiq javobi va obuna "
                f"eslatmalari shu yerga keladi."
            )
        else:
            telegram.send(
                chat_id,
                "Havola eskirgan yoki allaqachon ishlatilgan.\n\n"
                "Saytdagi profil sahifasidan yangi havola oling."
            )

    # Telegram HAR DOIM 200 kutadi — aks holda yangilanishni qayta-qayta
    # yuboraveradi.
    return JsonResponse({'ok': True})


def _error_response(request, exc: BillingError):
    """
    Xato javobi — HAR DOIM JSON.

    Ilgari oddiy so'rovga tarif sahifasi qaytarilardi. O'quvchi
    sahifalari React'ga ko'chgach bu ma'nosiz bo'lib qoldi: bu yerdagi
    ko'rinishlarni faqat tashqi xizmatlar va frontend chaqiradi,
    ikkalasi ham HTML kutmaydi.
    """
    return JsonResponse({'success': False, 'error': exc.message}, status=exc.status)
