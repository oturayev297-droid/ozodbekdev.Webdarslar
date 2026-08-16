"""
Hisobotlar
==========

Bu modulda FAQAT o'qish bor. Hech narsani o'zgartirmaydi. Shuning uchun
uni testda ham, konsolda ham bemalol chaqirsa bo'ladi.

MOLIYAVIY QOIDALAR (buzilsa hisobot yolg'on chiqadi):

1. TUSHUM FAQAT `SubscriptionPeriod` dan olinadi va faqat
   `source=PAYMENT` bo'lganlaridan. `ADMIN_GRANT` (bepul berilgan) va
   `TRIAL` — bu PUL EMAS. Ular qo'shilsa "tushum" o'ylab topilgan
   raqamga aylanadi.

2. Summa davrga MUZLATIB yozilgan `amount_tiyin` dan olinadi,
   `SubscriptionPlan.price_per_month_tiyin` dan EMAS. Aks holda narx
   ko'tarilgan kuni o'tgan oylarning tushumi ham "ko'tarilib" ketardi.

3. Aylanma sanasi — `created_at` (pul KELGAN payt), `start_date` emas
   (xizmat ko'rsatilgan davr). Kassa hisoboti pul kelgan kunga
   bog'lanadi.

4. Oylarga bo'lish Asia/Tashkent bo'yicha. UTC bo'yicha bo'linsa oyning
   birinchi kunidagi kechki to'lovlar o'tgan oyga tushib qolardi.

5. `PaymentRequest` — bu NIYAT, tushum emas. Tasdiqlanmagan so'rov
   hisobotga kirmaydi. Uni "kutilayotgan" sifatida alohida ko'rsatamiz.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from billing.dates import TASHKENT, format_money, now as billing_now
from billing.models import (
    OPEN_STATUSES,
    PaymentRequest,
    PeriodSource,
    RequestStatus,
    Subscription,
    SubscriptionPeriod,
)
from core.models import Certificate, Lesson, LoginAttempt, MentorMessage, QuizResult, UserProgress

#: Grafikda nechta oy ko'rsatiladi
DEFAULT_MONTHS = 12

#: "Tez orada tugaydi" chegarasi
EXPIRING_SOON_DAYS = 7


def _revenue_qs():
    """Tushum hisoblanadigan davrlar. Yagona manba — shu funksiya (1-qoida)."""
    return SubscriptionPeriod.objects.filter(
        source=PeriodSource.PAYMENT,
        amount_tiyin__isnull=False,
    )


def month_start(dt):
    """Berilgan vaqt tushadigan oyning boshi (Toshkent vaqti bilan)."""
    local = dt.astimezone(TASHKENT)
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def revenue_between(start, end) -> dict:
    """
    [start, end) oralig'idagi tushum.

    Chegara ATAYLAB yarim ochiq: oylar ketma-ket kelganda bir to'lov
    ikki oyga qo'shilib ketmasligi uchun.
    """
    agg = _revenue_qs().filter(created_at__gte=start, created_at__lt=end).aggregate(
        total=Sum('amount_tiyin'), count=Count('id')
    )
    total = agg['total'] or 0
    count = agg['count'] or 0
    return {
        'total_tiyin': total,
        'total_display': format_money(total),
        'count': count,
        'average_tiyin': total // count if count else 0,
    }


def monthly_series(months=DEFAULT_MONTHS, at=None) -> list:
    """
    Oxirgi N oy bo'yicha tushum qatori.

    To'lovi yo'q oy ham qatorda BO'LADI (nol bilan). Aks holda grafik
    oylarni o'tkazib yuborib, pasayishni ko'rsatmasdi.
    """
    at = at or billing_now()
    current = month_start(at)

    # N ta oy orqaga qaytamiz
    first = current
    for _ in range(months - 1):
        first = month_start(first - timedelta(days=1))

    rows = (
        _revenue_qs()
        .filter(created_at__gte=first)
        .annotate(bucket=TruncMonth('created_at', tzinfo=TASHKENT))
        .values('bucket')
        .annotate(total=Sum('amount_tiyin'), count=Count('id'))
    )
    by_month = {
        row['bucket'].astimezone(TASHKENT).strftime('%Y-%m'): row for row in rows if row['bucket']
    }

    series = []
    cursor = first
    while cursor <= current:
        key = cursor.strftime('%Y-%m')
        row = by_month.get(key)
        total = (row['total'] if row else 0) or 0
        series.append({
            'key': key,
            'label': cursor.strftime('%m.%Y'),
            'total_tiyin': total,
            'total_display': format_money(total),
            'count': (row['count'] if row else 0) or 0,
        })
        # Keyingi oyning boshiga o'tamiz: joriy oyning 28-kuniga 4 kun
        # qo'shsak har doim keyingi oyga tushamiz (fevral ham).
        cursor = month_start(cursor.replace(day=28) + timedelta(days=4))

    return series


def method_breakdown(start=None, end=None) -> list:
    """To'lov usullari kesimi: naqd, karta, Click, Payme."""
    qs = _revenue_qs()
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lt=end)

    rows = (
        qs.values('payment_method')
        .annotate(total=Sum('amount_tiyin'), count=Count('id'))
        .order_by('-total')
    )

    labels = dict(SubscriptionPeriod._meta.get_field('payment_method').choices or [])
    grand = sum((r['total'] or 0) for r in rows) or 1

    return [
        {
            'method': r['payment_method'],
            'label': labels.get(r['payment_method'], r['payment_method'] or "Noma'lum"),
            'total_tiyin': r['total'] or 0,
            'total_display': format_money(r['total'] or 0),
            'count': r['count'],
            'percent': round((r['total'] or 0) * 100 / grand, 1),
        }
        for r in rows
    ]


def granted_summary(start=None, end=None) -> dict:
    """
    Bepul berilgan davrlar.

    Tushumga KIRMAYDI, lekin ko'rinib turishi kerak: bepul berish ham
    xarajat — o'rnini bilmasdan tarif siyosatini o'zgartirib bo'lmaydi.
    """
    qs = SubscriptionPeriod.objects.filter(
        source__in=[PeriodSource.ADMIN_GRANT, PeriodSource.TRIAL]
    )
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lt=end)

    rows = qs.values('source').annotate(count=Count('id'))
    counts = {r['source']: r['count'] for r in rows}
    return {
        'trial': counts.get(PeriodSource.TRIAL, 0),
        'admin_grant': counts.get(PeriodSource.ADMIN_GRANT, 0),
        'total': sum(counts.values()),
    }


def subscriber_counts(at=None) -> dict:
    """
    Obunachilar holati.

    Holat SANADAN hisoblanadi — `billing.services.get_state` dagi bilan
    bir xil mantiq. Bayroq yo'q, shuning uchun bu yerda ham sana bilan
    solishtiramiz.
    """
    at = at or billing_now()
    soon = at + timedelta(days=EXPIRING_SOON_DAYS)

    qs = Subscription.objects.all()
    return {
        'total': qs.count(),
        'active': qs.filter(current_period_end__gt=at).count(),
        'expiring_soon': qs.filter(current_period_end__gt=at, current_period_end__lte=soon).count(),
        'expired': qs.filter(current_period_end__lte=at).count(),
        'never_paid': qs.filter(current_period_end__isnull=True).count(),
    }


def pending_requests() -> dict:
    """Kutayotgan to'lov so'rovlari — bu NIYAT, tushum emas (5-qoida)."""
    qs = PaymentRequest.objects.filter(status__in=[s.value for s in OPEN_STATUSES])
    rows = qs.values('status').annotate(count=Count('id'), total=Sum('amount_tiyin'))
    counts = {r['status']: r for r in rows}

    def part(status):
        row = counts.get(status.value, {})
        return {'count': row.get('count', 0), 'total_tiyin': row.get('total', 0) or 0}

    receipt = part(RequestStatus.RECEIPT_UPLOADED)
    return {
        'requested': part(RequestStatus.REQUESTED),
        'card_issued': part(RequestStatus.CARD_ISSUED),
        # Eng shoshilinchi: o'quvchi pulni YUBORGAN va javob kutmoqda
        'receipt_uploaded': receipt,
        'total': qs.count(),
        'needs_action': receipt['count'],
    }


def student_stats(at=None) -> dict:
    """O'quvchilar bo'yicha umumiy raqamlar."""
    at = at or timezone.now()
    week_ago = at - timedelta(days=7)
    month_ago = at - timedelta(days=30)

    return {
        'total': User.objects.filter(is_staff=False).count(),
        'new_week': User.objects.filter(is_staff=False, date_joined__gte=week_ago).count(),
        'new_month': User.objects.filter(is_staff=False, date_joined__gte=month_ago).count(),
        # "Faol" = oxirgi 7 kunda dars tugatgan yoki test topshirgan
        'active_week': (
            User.objects.filter(
                Q(progress__completed_at__gte=week_ago)
                | Q(quiz_results__completed_at__gte=week_ago)
            )
            .distinct()
            .count()
        ),
    }


def content_stats() -> dict:
    """Kontent hajmi."""
    lessons = Lesson.objects.all()
    return {
        'lessons': lessons.count(),
        'lessons_free': lessons.filter(is_free=True).count(),
        'lessons_with_video': lessons.filter(video_file__gt='').count(),
        'completions': UserProgress.objects.filter(is_completed=True).count(),
        'quiz_results': QuizResult.objects.count(),
        'certificates': Certificate.objects.filter(revoked_at__isnull=True).count(),
    }


def security_stats(at=None) -> dict:
    """Xavfsizlik: oxirgi 24 soatdagi urinishlar."""
    at = at or timezone.now()
    day_ago = at - timedelta(hours=24)

    qs = LoginAttempt.objects.filter(created_at__gte=day_ago)
    failed = qs.filter(successful=False)
    return {
        'attempts_24h': qs.count(),
        'failed_24h': failed.count(),
        # Ko'p urinilgan IP lar — hujum belgisi
        'top_failed_ips': list(
            failed.exclude(ip__isnull=True)
            .values('ip')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        ),
    }


def mentor_stats(at=None) -> dict:
    """AI Mentor foydalanishi — bu to'g'ridan-to'g'ri XARAJAT."""
    at = at or timezone.now()
    day_ago = at - timedelta(hours=24)
    month_ago = at - timedelta(days=30)

    return {
        'total': MentorMessage.objects.count(),
        'day': MentorMessage.objects.filter(created_at__gte=day_ago).count(),
        'month': MentorMessage.objects.filter(created_at__gte=month_ago).count(),
    }


def dashboard_context(at=None) -> dict:
    """Bosh sahifadagi barcha raqamlar — bitta joyda yig'iladi."""
    at = at or billing_now()
    this_month = month_start(at)
    next_month = month_start(this_month.replace(day=28) + timedelta(days=4))
    prev_month = month_start(this_month - timedelta(days=1))

    current = revenue_between(this_month, next_month)
    previous = revenue_between(prev_month, this_month)

    # O'tgan oyga nisbatan o'zgarish. Baza nol bo'lsa foiz ma'nosiz —
    # None qaytaramiz va shablon uni ko'rsatmaydi.
    if previous['total_tiyin']:
        change = round(
            (current['total_tiyin'] - previous['total_tiyin']) * 100 / previous['total_tiyin'], 1
        )
    else:
        change = None

    return {
        'revenue_month': current,
        'revenue_prev_month': previous,
        'revenue_change_percent': change,
        'revenue_total': revenue_between(
            SubscriptionPeriod.objects.order_by('created_at')
            .values_list('created_at', flat=True)
            .first()
            or at,
            at + timedelta(days=1),
        ),
        'subscribers': subscriber_counts(at),
        'requests': pending_requests(),
        'students': student_stats(),
        'content': content_stats(),
        'security': security_stats(),
        'mentor': mentor_stats(),
        'granted': granted_summary(this_month, next_month),
    }
