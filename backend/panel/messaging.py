"""
Xabar yuborish
==============

QOIDALAR:

1. YUBORISH IKKI BOSQICHLI. Avval har bir oluvchi uchun `PanelDelivery`
   qatori YOZILADI (bitta tranzaksiyada), keyin yuboriladi. Shu sabab
   yuborish yarmida uzilsa (server qayta yuklandi, Telegram javob
   bermadi) qolgani YO'QOLMAYDI — navbatda turaveradi.

2. TAKRORLANMAYDI. `(message, user)` unique. Yuborish qayta ishga
   tushsa ham bir odam bitta xabarni ikki marta olmaydi.

3. VAQT BUDJETI. Panel tugmasi yuborishni DARHOL boshlaydi, lekin
   belgilangan soniyadan ortiq ushlab turmaydi — aks holda 300 kishilik
   xabar so'rovni gunicorn timeout'iga olib borardi. Qolgani
   `send_panel_messages` buyrug'i bilan yuboriladi.

4. TELEGRAMI YO'Q O'QUVCHI OLUVCHI EMAS. U umuman ro'yxatga
   qo'shilmaydi — "yuborildi" deb yozib qo'yish yolg'on hisobot
   bo'lardi. Panel auditoriyani tanlashda nechta odam Telegramsiz
   ekanini ko'rsatadi.

5. MATN O'ZGARTIRILMAYDI. Telegramga qanday yozilgan bo'lsa shundayligicha
   ketadi (parse_mode ishlatilmaydi) — o'qituvchi yozgan apostrof yoki
   pastki chiziq xabarni buzmasin.
"""

import logging
import time
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from billing import telegram
from billing.dates import now as billing_now
from billing.models import Subscription

from .models import Audience, MessageStatus, PanelDelivery, PanelMessage
from .reports import EXPIRING_SOON_DAYS

logger = logging.getLogger(__name__)

#: Panel tugmasi bosilganda yuborishga ajratiladigan vaqt (soniya).
#: Gunicorn odatda 30 soniyada uzadi — yarmidan kamini olamiz.
SYNC_BUDGET_SECONDS = 10

#: Bitta xabarning eng katta uzunligi. Telegram chegarasi 4096.
MAX_BODY_LENGTH = 3500


class MessagingError(Exception):
    """Foydalanuvchiga ko'rsatiladigan xato."""


def audience_queryset(audience, target_user=None, at=None):
    """
    Auditoriya bo'yicha foydalanuvchilar.

    Telegrami ULANGANLAR bilan cheklanadi (4-qoida).
    """
    at = at or billing_now()

    linked = User.objects.filter(
        is_active=True,
        profile__telegram_chat_id__gt='',
    )

    if audience == Audience.ONE:
        if target_user is None:
            raise MessagingError("O'quvchi tanlanmagan.")
        return linked.filter(pk=target_user.pk)

    if audience == Audience.ALL:
        return linked

    if audience == Audience.ACTIVE:
        return linked.filter(subscription__current_period_end__gt=at)

    if audience == Audience.EXPIRING:
        soon = at + timedelta(days=EXPIRING_SOON_DAYS)
        return linked.filter(
            subscription__current_period_end__gt=at,
            subscription__current_period_end__lte=soon,
        )

    if audience == Audience.EXPIRED:
        return linked.filter(subscription__current_period_end__lte=at)

    raise MessagingError("Auditoriya noto'g'ri.")


def audience_preview(at=None) -> dict:
    """
    Har bir auditoriyada nechta odam borligi — tugmani bosishdan OLDIN.

    Telegramsizlar soni ham ko'rsatiladi: "hammaga yubordim" deb
    o'ylab, aslida yarmi olmay qolishi eng yomon holat.
    """
    at = at or billing_now()
    rows = []
    for audience in (Audience.ALL, Audience.ACTIVE, Audience.EXPIRING, Audience.EXPIRED):
        rows.append({
            'value': audience.value,
            'label': audience.label,
            'count': audience_queryset(audience, at=at).count(),
        })

    total_students = User.objects.filter(is_active=True, is_staff=False).count()
    linked = User.objects.filter(
        is_active=True, is_staff=False, profile__telegram_chat_id__gt=''
    ).count()
    return {
        'rows': rows,
        'total_students': total_students,
        'linked': linked,
        'unlinked': total_students - linked,
    }


@transaction.atomic
def create_message(sent_by, audience, body, target_user=None) -> PanelMessage:
    """
    Xabarni va uning yetkazish qatorlarini yozadi. HALI YUBORMAYDI.

    Bitta tranzaksiyada: yarim yozilgan xabar qolib ketmasin.
    """
    body = (body or '').strip()
    if not body:
        raise MessagingError("Xabar matni bo'sh.")
    if len(body) > MAX_BODY_LENGTH:
        raise MessagingError(
            f"Xabar juda uzun ({len(body)} belgi). Eng ko'pi {MAX_BODY_LENGTH} belgi."
        )
    if not telegram.is_configured():
        raise MessagingError(
            "Telegram bot sozlanmagan. `.env` da TELEGRAM_BOT_TOKEN to'ldirilishi kerak."
        )

    recipients = list(
        audience_queryset(audience, target_user).select_related('profile').distinct()
    )
    if not recipients:
        raise MessagingError("Bu auditoriyada Telegrami ulangan o'quvchi yo'q.")

    message = PanelMessage.objects.create(
        sent_by=sent_by,
        audience=audience,
        target_user=target_user,
        body=body,
        total=len(recipients),
    )

    PanelDelivery.objects.bulk_create([
        PanelDelivery(
            message=message,
            user=user,
            chat_id=user.profile.telegram_chat_id or '',
        )
        for user in recipients
    ])

    return message


def deliver(message, budget_seconds=None) -> dict:
    """
    Navbatdagi qatorlarni yuboradi.

    `budget_seconds` berilsa shu vaqtdan keyin TO'XTAYDI va qolgani
    navbatda qoladi (3-qoida). Berilmasa — hammasi yuborilguncha
    ishlaydi (buyruq shunday chaqiradi).
    """
    started = time.monotonic()
    sent = failed = 0

    pending = message.deliveries.filter(state=PanelDelivery.State.PENDING).select_related('user')

    for delivery in pending.iterator():
        if budget_seconds is not None and (time.monotonic() - started) >= budget_seconds:
            break

        if not delivery.chat_id:
            delivery.state = PanelDelivery.State.FAILED
            delivery.error = "Telegram ulanmagan"
            delivery.save(update_fields=['state', 'error'])
            failed += 1
            continue

        ok = telegram.send(delivery.chat_id, message.body)
        if ok:
            delivery.state = PanelDelivery.State.SENT
            delivery.sent_at = timezone.now()
            delivery.error = ''
            sent += 1
        else:
            delivery.state = PanelDelivery.State.FAILED
            delivery.error = "Telegram qabul qilmadi"
            failed += 1
        delivery.save(update_fields=['state', 'sent_at', 'error'])

    _refresh_counters(message)
    return {'sent': sent, 'failed': failed, 'pending': message.pending_count}


def _refresh_counters(message):
    """
    Hisoblagichlarni qatorlardan QAYTA sanaydi.

    Oshirib borish o'rniga qayta sanash: yuborish bir necha marta
    uzilib-ulanganda oshirish xato beradi, qayta sanash esa har doim
    to'g'ri.
    """
    states = message.deliveries.values_list('state', flat=True)
    message.delivered = sum(1 for s in states if s == PanelDelivery.State.SENT)
    message.failed = sum(1 for s in states if s == PanelDelivery.State.FAILED)

    if message.delivered + message.failed >= message.total:
        message.status = MessageStatus.FAILED if message.delivered == 0 else MessageStatus.DONE
        message.finished_at = timezone.now()
    else:
        message.status = MessageStatus.PENDING
        message.finished_at = None

    message.save(update_fields=['delivered', 'failed', 'status', 'finished_at'])


def send_now(sent_by, audience, body, target_user=None) -> PanelMessage:
    """Panel tugmasi shu funksiyani chaqiradi: yozadi va darhol boshlaydi."""
    message = create_message(sent_by, audience, body, target_user)
    deliver(message, budget_seconds=SYNC_BUDGET_SECONDS)
    message.refresh_from_db()
    return message


def deliver_all_pending(budget_seconds=None) -> dict:
    """Navbatda qolgan barcha xabarlar — buyruq uchun."""
    totals = {'messages': 0, 'sent': 0, 'failed': 0}
    for message in PanelMessage.objects.filter(status=MessageStatus.PENDING).order_by('created_at'):
        result = deliver(message, budget_seconds=budget_seconds)
        totals['messages'] += 1
        totals['sent'] += result['sent']
        totals['failed'] += result['failed']
    return totals
