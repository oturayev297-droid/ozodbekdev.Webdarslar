"""
Kunlik obuna vazifalari.

Ikki ish bajaradi:
  1. Javobsiz qolgan to'lov so'rovlarini kuydiradi (EXPIRED)
  2. Muddati yaqinlashgan o'quvchilarga eslatma yuboradi (7, 3, 0 kun)

Har chegara BIR MARTA: `last_reminder_days_left` shu uchun bor. Busiz
kunlik yurish har kuni o'sha xabarni qayta yuborardi.

cron / Task Scheduler da kuniga bir marta:
    python manage.py subscription_daily
"""

import logging

from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from billing import dates
from billing.models import Subscription
from billing.payment_requests import expire_stale_requests
from billing.services import get_plan

logger = logging.getLogger(__name__)

#: Eslatma yuboriladigan chegaralar (kun)
REMIND_AT = (7, 3, 0)


class Command(BaseCommand):
    help = "Javobsiz so'rovlarni kuydiradi va obuna eslatmalarini yuboradi"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Hech narsa o'zgartirmasdan, faqat nima bo'lishini ko'rsatadi",
        )

    def handle(self, *args, **options):
        dry = options['dry_run']

        # ── 1. Javobsiz so'rovlar ──
        if dry:
            from billing.models import PaymentRequest, RequestStatus
            count = PaymentRequest.objects.filter(
                status__in=[RequestStatus.REQUESTED, RequestStatus.CARD_ISSUED],
                expires_at__lt=dates.now(),
            ).count()
            self.stdout.write(f"[dry-run] {count} ta so'rov kuydirilardi")
        else:
            count = expire_stale_requests()
            self.stdout.write(f"Kuydirilgan so'rovlar: {count}")

        # ── 2. Eslatmalar ──
        plan = get_plan()
        stats = {'checked': 0, 'reminded': 0, 'expired': 0, 'no_email': 0}

        subscriptions = (
            Subscription.objects.select_related('user', 'plan')
            .filter(current_period_end__isnull=False)
        )

        for sub in subscriptions:
            stats['checked'] += 1
            left = dates.days_left(sub.current_period_end)

            if left < 0:
                stats['expired'] += 1
                continue

            # Qaysi chegaraga tushdi
            threshold = next((t for t in REMIND_AT if left <= t), None)
            if threshold is None:
                continue

            # Shu chegara uchun allaqachon yuborilgan
            if sub.last_reminder_days_left is not None and sub.last_reminder_days_left <= threshold:
                continue

            if not sub.user.email:
                stats['no_email'] += 1
                continue

            if dry:
                self.stdout.write(
                    f"[dry-run] {sub.user.username}: {left} kun qoldi "
                    f"(chegara {threshold})"
                )
                stats['reminded'] += 1
                continue

            if self._send_reminder(sub, left, plan):
                sub.last_reminder_days_left = threshold
                sub.save(update_fields=['last_reminder_days_left', 'updated_at'])
                stats['reminded'] += 1

        self.stdout.write(self.style.SUCCESS(
            f"Tekshirildi: {stats['checked']}, eslatma: {stats['reminded']}, "
            f"tugagan: {stats['expired']}, emailsiz: {stats['no_email']}"
        ))

    def _send_reminder(self, sub, left, plan) -> bool:
        end = dates.format_date(sub.current_period_end)

        if left == 0:
            subject = "Nexus — obunangiz bugun tugaydi"
            body = (
                f"Assalomu alaykum!\n\n"
                f"Obunangiz bugun ({end}) tugaydi.\n\n"
                f"Yana {plan.grace_days} kun kirishingiz ochiq qoladi, "
                f"undan keyin bepul darslardan boshqasi yopiladi.\n\n"
                f"Uzaytirish: obuna bo'limiga o'tib muddatni tanlang.\n"
            )
        else:
            subject = f"Nexus — obunangizga {left} kun qoldi"
            body = (
                f"Assalomu alaykum!\n\n"
                f"Obunangiz {end} kuni tugaydi — {left} kun qoldi.\n\n"
                f"Uzaytirish uchun obuna bo'limiga o'tib muddatni tanlang. "
                f"Muddat tugamasdan to'lasangiz qolgan kunlaringiz "
                f"yo'qolmaydi — yangi muddat eski sanadan qo'shiladi.\n"
            )

        try:
            send_mail(subject, body, None, [sub.user.email], fail_silently=False)
            logger.info("[OBUNA] Eslatma yuborildi: %s (%s kun)", sub.user.username, left)
            return True
        except Exception as exc:
            logger.error("[OBUNA] Eslatma yuborilmadi (%s): %s", sub.user.username, exc)
            return False
