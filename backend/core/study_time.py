"""
O'quv vaqtini o'lchash
======================

QANDAY ISHLAYDI: ochiq sahifa har daqiqada bir marta "men shu
yerdaman" degan signal yuboradi. Har signal kunlik hisobga bir
oraliq qo'shadi.

NEGA "BOSHLANDI/TUGADI" EMAS: tab yopilganda "tugadi" signali
KAFOLATLANMAYDI — kompyuter o'chishi, internet uzilishi, brauzer
qotishi mumkin. O'shanda ochiq qolgan seans soatlab hisoblanib
ketardi va hisobot yolg'on chiqardi. Vaqti-vaqti bilan keladigan
signal esa eng yomon holatda BITTA oraliqni yo'qotadi.

ISHONCH QOIDALARI (buzilsa raqamlar soxtalashadi):

1. SANA SERVERDA hisoblanadi. Klientdan olinsa, uni o'zgartirib
   "kecha 10 soat o'qidim" deb yozib qo'yish mumkin bo'lardi.
2. HAR SIGNAL UCHUN QAT'IY MIQDOR qo'shiladi, klient aytgan miqdor
   emas. Aks holda bitta so'rov bilan istalgancha vaqt yozib
   olinardi.
3. JUDA TEZ KELGAN SIGNAL E'TIBORSIZ QOLDIRILADI. Skript yozib
   sekundiga o'nlab signal yuborish bilan soatlab vaqt to'plash
   mumkin bo'lmasin.
4. KUNLIK SHIFT bor. Texnik nosozlik yoki hiyla tufayli bir kunda
   24 soatdan ko'p yozilib qolmasin.
"""

import logging
from datetime import date as date_type, timedelta

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from billing.dates import TASHKENT

from .models import StudySession

logger = logging.getLogger(__name__)

#: Har signal shuncha soniya qo'shadi. Frontend har daqiqada yuboradi,
#: shuning uchun 60. Signal kechiksa ham ortiqcha yozilmaydi.
SECONDS_PER_PING = 60

#: Ikki signal orasidagi ENG KAM vaqt. Bundan tez kelgani hisobga
#: olinmaydi — bu 3-qoida.
MIN_INTERVAL_SECONDS = 45

#: Bir kunda yozilishi mumkin bo'lgan eng ko'p vaqt (4-qoida).
#: 14 soat — real chegara: bundan ko'pi texnik nosozlik yoki hiyla.
MAX_SECONDS_PER_DAY = 14 * 60 * 60


def today() -> date_type:
    """Toshkent vaqti bo'yicha BUGUN. Sana faqat shu yerdan olinadi."""
    return timezone.now().astimezone(TASHKENT).date()


def record_ping(user) -> dict:
    """
    Bitta "men shu yerdaman" signalini yozadi.

    Qaytaradi: bugungi jami soniya va signal hisobga olindimi.
    """
    date = today()

    with transaction.atomic():
        session, created = StudySession.objects.select_for_update().get_or_create(
            user=user, date=date
        )

        if not created:
            # JUDA TEZ KELGAN SIGNALNI RAD ETAMIZ (3-qoida).
            # `updated_at` oxirgi yozuv vaqti — undan beri yetarli
            # vaqt o'tmagan bo'lsa, bu takroriy yoki soxta signal.
            since = (timezone.now() - session.updated_at).total_seconds()
            if since < MIN_INTERVAL_SECONDS:
                return {
                    'counted': False,
                    'seconds_today': session.seconds,
                    'reason': 'too_soon',
                }

        if session.seconds >= MAX_SECONDS_PER_DAY:
            logger.warning(
                "[VAQT] %s kunlik chegaraga yetdi (%s soniya)", user.username, session.seconds
            )
            return {
                'counted': False,
                'seconds_today': session.seconds,
                'reason': 'daily_limit',
            }

        # `F()` bilan: ikki so'rov bir vaqtda kelsa ham biri
        # ikkinchisining yozuvini o'chirib yubormaydi.
        StudySession.objects.filter(pk=session.pk).update(
            seconds=F('seconds') + SECONDS_PER_PING
        )
        session.refresh_from_db(fields=['seconds'])

    return {'counted': True, 'seconds_today': session.seconds, 'reason': ''}


def record_lesson_completed(user) -> None:
    """
    Dars tugatilganini kunlik hisobga qo'shadi.

    NEGA KERAK: "3 soat o'tirdi, lekin bitta dars tugatmadi" degan
    holat ota-onaga ko'rinishi kerak. Vaqtning o'zi o'zlashtirishni
    ko'rsatmaydi.
    """
    date = today()
    session, _ = StudySession.objects.get_or_create(user=user, date=date)
    StudySession.objects.filter(pk=session.pk).update(
        lessons_completed=F('lessons_completed') + 1
    )


def daily_series(user, days=14) -> list:
    """
    Oxirgi N kun bo'yicha qator.

    Yozuvi yo'q kun ham qatorda BO'LADI (nol bilan). Aks holda grafik
    kunlarni o'tkazib yuborib, tanaffusni ko'rsatmasdi — ota-ona esa
    aynan shuni ko'rmoqchi.
    """
    end = today()
    start = end - timedelta(days=days - 1)

    rows = {
        row.date: row
        for row in StudySession.objects.filter(user=user, date__gte=start, date__lte=end)
    }

    series = []
    for offset in range(days):
        date = start + timedelta(days=offset)
        row = rows.get(date)
        series.append({
            'date': date.isoformat(),
            'label': date.strftime('%d.%m'),
            'seconds': row.seconds if row else 0,
            'minutes': row.minutes if row else 0,
            'hours': row.hours if row else 0.0,
            'lessons_completed': row.lessons_completed if row else 0,
        })
    return series


def summary(user, days=30) -> dict:
    """Umumiy raqamlar: jami vaqt, o'rtacha, faol kunlar."""
    end = today()
    start = end - timedelta(days=days - 1)

    rows = list(StudySession.objects.filter(user=user, date__gte=start, date__lte=end))
    total_seconds = sum(r.seconds for r in rows)
    active_days = sum(1 for r in rows if r.seconds > 0)

    today_row = next((r for r in rows if r.date == end), None)

    return {
        'today_minutes': today_row.minutes if today_row else 0,
        'total_seconds': total_seconds,
        'total_hours': round(total_seconds / 3600, 1),
        'active_days': active_days,
        # O'rtacha FAQAT FAOL kunlar bo'yicha: nol kunlarni qo'shsak,
        # bir kun 3 soat o'qigan bola "kuniga 6 daqiqa" bo'lib
        # ko'rinardi va bu chalg'itardi.
        'average_minutes': round(total_seconds / 60 / active_days) if active_days else 0,
        'all_time_hours': round(
            (StudySession.objects.filter(user=user).aggregate(t=Sum('seconds'))['t'] or 0) / 3600,
            1,
        ),
    }
