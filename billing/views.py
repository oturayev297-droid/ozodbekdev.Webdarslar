"""O'quvchi tomonidagi obuna sahifalari."""

import json
import logging
import secrets

from django.conf import settings as dj_settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import dates, payment_requests, telegram
from .models import PeriodSource, ReceiptSource, RequestStatus
from .services import BillingError, STATUS_LABELS, get_plan, get_state

logger = logging.getLogger(__name__)


def _error_response(request, exc: BillingError):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({'success': False, 'error': exc.message}, status=exc.status)
    messages.error(request, exc.message)
    return redirect('billing:plans')


@login_required
def plans(request):
    """
    Tarif sahifasi.

    Narxlar SERVERDA hisoblanadi va shablonga tayyor holda beriladi —
    klientda `narx * oy` yozilmaydi, aks holda hisob ikki joyda
    takrorlanardi.
    """
    plan = get_plan()
    state = get_state(request.user)
    open_request = payment_requests.get_open_request(request.user)

    options = [
        {
            'months': m,
            'amount_tiyin': plan.price_for(m),
            'amount_display': dates.format_money(plan.price_for(m)),
            'per_month_display': dates.format_money(plan.price_per_month_tiyin),
            'preview_end': dates.format_date(
                dates.add_months(dates.extension_base(state.current_period_end), m)
            ),
        }
        for m in dates.ALLOWED_MONTHS
    ]

    # Karta rekvizitlari FAQAT so'rovi CARD_ISSUED bo'lganda ko'rinadi
    cards = []
    if open_request and open_request.status == RequestStatus.CARD_ISSUED:
        cards = payment_requests.get_card_for_user(request.user)['cards']

    return render(request, 'billing/plans.html', {
        'plan': plan,
        'state': state,
        'status_label': STATUS_LABELS.get(state.status, state.status),
        'options': options,
        'open_request': open_request,
        'cards': cards,
        'receipt_sources': ReceiptSource.choices,
    })


@login_required
@require_POST
def create_request(request):
    try:
        req = payment_requests.create_request(request.user, request.POST.get('months'))
    except BillingError as exc:
        return _error_response(request, exc)

    messages.success(
        request,
        f"So'rovingiz qabul qilindi ({req.months} oy — {dates.format_money(req.amount_tiyin)}). "
        "Administrator karta rekvizitlarini beradi.",
    )
    return redirect('billing:plans')


@login_required
@require_POST
def mark_receipt_sent(request):
    try:
        payment_requests.mark_receipt_sent(request.user, request.POST.get('source'))
    except BillingError as exc:
        return _error_response(request, exc)

    plan = get_plan()
    messages.success(
        request,
        "Rahmat! Administrator to'lovingizni tekshiradi. Shu vaqt ichida "
        f"({plan.pending_hold_days} kun) kirishingiz ochiq qoladi.",
    )
    return redirect('billing:plans')


@login_required
@require_POST
def cancel_request(request):
    """O'quvchi o'z so'rovini bekor qiladi (hali chek yubormagan bo'lsa)."""
    req = payment_requests.get_open_request(request.user)
    if not req:
        messages.error(request, "Ochiq so'rov topilmadi.")
    elif req.status == RequestStatus.RECEIPT_UPLOADED:
        messages.error(
            request,
            "Chek yuborilgan so'rovni bekor qilib bo'lmaydi — administrator "
            "tekshirmoqda.",
        )
    else:
        req.status = RequestStatus.EXPIRED
        req.save(update_fields=['status', 'updated_at'])
        messages.success(request, "So'rov bekor qilindi.")

    return redirect('billing:plans')


@login_required
@require_POST
def telegram_link(request):
    """Telegram hisobini ulash uchun bir martalik havola beradi."""
    url = telegram.create_link_token(request.user)
    return JsonResponse({'success': True, 'url': url})


@login_required
@require_POST
def telegram_unlink(request):
    """Ulanishni uzadi."""
    profile = request.user.profile
    profile.telegram_chat_id = ''
    profile.save(update_fields=['telegram_chat_id'])
    messages.success(request, "Telegram ulanishi uzildi.")
    return redirect('profile')


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


@login_required
def my_history(request):
    """O'quvchining to'lov va davr tarixi."""
    from .models import Subscription

    subscription = Subscription.objects.filter(user=request.user).first()
    periods = (
        subscription.periods.select_related('plan').order_by('-created_at')
        if subscription else []
    )
    requests_list = request.user.payment_requests.order_by('-requested_at')[:20]

    return render(request, 'billing/history.html', {
        'state': get_state(request.user),
        'periods': periods,
        'requests': requests_list,
    })
