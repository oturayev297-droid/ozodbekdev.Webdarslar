"""
Ota-onaga haftalik hisobot (Telegram).

Ota-ona `/farzandlarim` sahifasiga har kuni kirib ko'rmaydi. Haftada
bir marta o'zi keladigan qisqa xabar — panelning asosiy foydasi
aynan shu: ota-ona bolaning o'qishdan uzoqlashganini kech emas,
o'sha haftada biladi.

XABAR FAQAT BOG'LANGAN OTA-ONAGA BORADI. `ParentLink` ni admin
yaratadi — ya'ni bu yerda huquq qayta tekshirilmaydi, u allaqachon
bog'lanishning o'zida.

cron da haftada bir marta (masalan dushanba ertalab):
    python manage.py parent_weekly_report
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count

from billing import telegram
from core import study_time
from core.models import Lesson, ParentLink, QuizResult, UserProgress

logger = logging.getLogger(__name__)

#: Hisobot qamrab oladigan kunlar
PERIOD_DAYS = 7


def build_message(link) -> str:
    """
    Bitta bog'lanish uchun xabar matni.

    HTML `parse_mode` ishlatiladi (`telegram.send` shunday yuboradi),
    shuning uchun ism `<b>` ichida — foydalanuvchi kiritgan matn
    Telegram tomonidan teg deb o'qilmasligi uchun `<` va `>` almashtiriladi.
    """
    student = link.student
    name = (student.profile.full_name or student.username).replace('<', '').replace('>', '')

    summary = study_time.summary(student, days=PERIOD_DAYS)

    since = study_time.today() - timedelta(days=PERIOD_DAYS - 1)
    quizzes = QuizResult.objects.filter(
        user=student, completed_at__date__gte=since
    ).aggregate(taken=Count('id'), average=Avg('score_percentage'))

    total_lessons = Lesson.objects.count()
    completed = UserProgress.objects.filter(user=student, is_completed=True).count()
    percent = round(completed * 100 / total_lessons) if total_lessons else 0

    lines = [
        f"<b>{name}</b> — haftalik hisobot",
        "",
        f"O'qigan vaqti: <b>{summary['total_hours']} soat</b>"
        f" ({summary['active_days']} kun)",
    ]

    if quizzes['taken']:
        lines.append(
            f"Test: <b>{quizzes['taken']} ta</b>, "
            f"o'rtacha ball <b>{round(quizzes['average'])}%</b>"
        )
    else:
        lines.append("Test topshirmagan")

    lines.append(f"O'zlashtirish: <b>{percent}%</b> ({completed}/{total_lessons} dars)")

    # HAFTA BO'SH O'TGAN BO'LSA buni ochiq aytamiz. Quruq nollar
    # ro'yxatidan ko'ra bitta jumla tushunarli va aynan shu holat
    # uchun ota-onaga xabar kerak.
    if not summary['active_days']:
        lines += ["", "Bu hafta darsga kirmadi."]

    return "\n".join(lines)


class Command(BaseCommand):
    help = "Ota-onalarga farzandi haqida haftalik hisobot yuboradi"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Yubormasdan, xabar matnini ko'rsatadi",
        )

    def handle(self, *args, **options):
        dry = options['dry_run']

        if not dry and not telegram.is_configured():
            self.stdout.write(self.style.WARNING(
                "Telegram sozlanmagan (TELEGRAM_BOT_TOKEN bo'sh) — hech narsa yuborilmadi."
            ))
            return

        links = ParentLink.objects.select_related(
            'parent__profile', 'student__profile'
        ).order_by('parent__username')

        stats = {'links': 0, 'sent': 0, 'no_chat': 0, 'failed': 0}

        for link in links:
            stats['links'] += 1

            chat_id = telegram.user_chat_id(link.parent)
            if not chat_id:
                # Ota-ona Telegramni ulamagan. Bu xato emas —
                # hisobotni sahifadan ko'rishda davom etadi.
                stats['no_chat'] += 1
                continue

            text = build_message(link)

            if dry:
                self.stdout.write(f"\n--- {link.parent.username} ---\n{text}")
                stats['sent'] += 1
                continue

            if telegram.send(chat_id, text):
                stats['sent'] += 1
            else:
                stats['failed'] += 1

        prefix = '[dry-run] ' if dry else ''
        self.stdout.write(
            f"{prefix}Bog'lanish: {stats['links']}, yuborildi: {stats['sent']}, "
            f"Telegram ulanmagan: {stats['no_chat']}, xato: {stats['failed']}"
        )
        logger.info("[HISOBOT] Haftalik ota-ona hisoboti: %s", stats)
