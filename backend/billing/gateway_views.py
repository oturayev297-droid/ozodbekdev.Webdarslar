"""
To'lov tizimlari endpointlari.

Bu ko'rinishlar TASHQI serverlar tomonidan chaqiriladi (Payme, Click),
shuning uchun:
  * `csrf_exempt` — sessiya va CSRF tokeni yo'q;
  * autentifikatsiya har tizimning O'Z usuli bilan (Payme: Basic auth,
    Click: MD5 imzo);
  * javob HAR DOIM 200 bo'ladi, xato ham javob TANASIDA qaytariladi —
    ikkala tizim ham HTTP xato kodini "tarmoq nosozligi" deb tushunib
    so'rovni cheksiz qayta yuboraveradi.
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .gateways import click as click_gw
from .gateways import payme as payme_gw

logger = logging.getLogger(__name__)


# ==========================================================================
# Payme — JSON-RPC 2.0
# ==========================================================================


def _rpc_error(request_id, code, message, data=None):
    error = {'code': code, 'message': message}
    if data is not None:
        error['data'] = data
    return JsonResponse({'jsonrpc': '2.0', 'id': request_id, 'error': error})


@csrf_exempt
def payme_endpoint(request):
    """Payme Merchant API. Barcha metodlar shu manzilga keladi."""
    if request.method != 'POST':
        return _rpc_error(None, payme_gw.ERR_TRANSPORT, payme_gw._msg("Faqat POST"))

    # AUTENTIFIKATSIYA BIRINCHI: tanani o'qishdan ham oldin. Aks holda
    # begona so'rov bilan tizim holati haqida xulosa chiqarib bo'lardi.
    if not payme_gw.check_auth(request.headers.get('Authorization', '')):
        logger.warning("[PAYME] Ruxsatsiz so'rov")
        return _rpc_error(
            None, payme_gw.ERR_UNAUTHORIZED,
            payme_gw._msg("Ruxsat yo'q", "Недостаточно привилегий", "Insufficient privileges"),
        )

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _rpc_error(None, payme_gw.ERR_PARSE, payme_gw._msg("JSON o'qilmadi"))

    request_id = payload.get('id')
    method = payload.get('method')
    params = payload.get('params') or {}

    handler = payme_gw.METHODS.get(method)
    if handler is None:
        return _rpc_error(
            request_id, payme_gw.ERR_METHOD_NOT_FOUND,
            payme_gw._msg("Metod topilmadi", "Метод не найден", "Method not found"),
        )

    try:
        result = handler(params)
    except payme_gw.PaymeError as exc:
        return _rpc_error(request_id, exc.code, exc.message, exc.data)
    except Exception:
        # Kutilmagan xato ham JSON-RPC xatosi bo'lib qaytishi kerak.
        # Aks holda Django 500 sahifasini HTML da qaytarardi va Payme
        # uni tushunmasdan so'rovni qayta-qayta yuboraverardi.
        logger.exception("[PAYME] Kutilmagan xato: metod=%s", method)
        return _rpc_error(
            request_id, payme_gw.ERR_INTERNAL,
            payme_gw._msg("Tizim xatosi", "Внутренняя ошибка", "Internal error"),
        )

    return JsonResponse({'jsonrpc': '2.0', 'id': request_id, 'result': result})


# ==========================================================================
# Click — SHOP API
# ==========================================================================


def _click_call(request, handler):
    # Click ma'lumotni form-data sifatida yuboradi
    data = request.POST.dict() if request.POST else {}
    if not data and request.body:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}

    try:
        return JsonResponse(handler(data))
    except click_gw.ClickResult as exc:
        return JsonResponse(click_gw.error_response(data, exc.code))
    except Exception:
        logger.exception("[CLICK] Kutilmagan xato")
        return JsonResponse(click_gw.error_response(data, click_gw.ERR_BAD_REQUEST))


@csrf_exempt
@require_POST
def click_prepare(request):
    return _click_call(request, click_gw.prepare)


@csrf_exempt
@require_POST
def click_complete(request):
    return _click_call(request, click_gw.complete)
