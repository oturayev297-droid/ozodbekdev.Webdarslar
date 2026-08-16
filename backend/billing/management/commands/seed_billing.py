"""
Obuna tizimini boshlang'ich holatga keltiradi.

Ishga tushirish:
    python manage.py seed_billing
    python manage.py seed_billing --price 100000 --free-lessons 3
"""

import json

from django.core.management.base import BaseCommand
from django.db import transaction

from billing import dates
from billing.models import AdminSetting
from billing.services import CARDS_KEY, get_plan
from core.models import Category, Lesson


class Command(BaseCommand):
    help = "Tarifni yaratadi va har yo'nalishning dastlabki darslarini bepul qiladi"

    def add_arguments(self, parser):
        parser.add_argument(
            '--price', type=int, default=None,
            help="Oylik narx SO'MDA (masalan 100000). Berilmasa o'zgarmaydi.",
        )
        parser.add_argument(
            '--free-lessons', type=int, default=3,
            help="Har yo'nalishda nechta dastlabki dars bepul bo'lsin (standart 3)",
        )
        parser.add_argument(
            '--trial-days', type=int, default=None,
            help="Sinov kunlari. 0 = avtomatik berilmaydi (standart).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        plan = get_plan()

        if options['price'] is not None:
            plan.price_per_month_tiyin = options['price'] * 100
        if options['trial_days'] is not None:
            plan.trial_days = options['trial_days']
        plan.save()

        self.stdout.write(self.style.SUCCESS(
            f"Tarif: {plan.name} — {dates.format_money(plan.price_per_month_tiyin)}/oy"
        ))
        for m in dates.ALLOWED_MONTHS:
            self.stdout.write(f"    {m:>2} oy -> {dates.format_money(plan.price_for(m))}")
        self.stdout.write(
            f"  sinov={plan.trial_days} kun, muhlat={plan.grace_days} kun, "
            f"kutish={plan.pending_hold_days} kun"
        )

        # ── Bepul darslar ──
        n = options['free_lessons']
        self.stdout.write("")

        # Avval hammasini yopamiz — buyruq qayta ishga tushirilsa natija
        # bir xil bo'lsin (idempotent), aks holda bepul darslar yig'ilib
        # ketardi.
        Lesson.objects.update(is_free=False)

        total_free = 0
        for category in Category.objects.all():
            lesson_ids = list(
                Lesson.objects.filter(module__category=category)
                .order_by('module__order', 'order', 'id')
                .values_list('id', flat=True)[:n]
            )
            Lesson.objects.filter(id__in=lesson_ids).update(is_free=True)
            total_free += len(lesson_ids)
            self.stdout.write(
                f"  {category.slug}: {len(lesson_ids)} bepul / "
                f"{Lesson.objects.filter(module__category=category).count()} dars"
            )

        self.stdout.write(self.style.SUCCESS(f"\nJami {total_free} bepul dars."))

        # ── Karta rekvizitlari ──
        if not AdminSetting.objects.filter(key=CARDS_KEY).exists():
            AdminSetting.objects.create(
                key=CARDS_KEY,
                value=json.dumps([], ensure_ascii=False),
            )
            self.stdout.write(self.style.WARNING(
                f"\nDIQQAT: karta rekvizitlari bo'sh. Admin panel -> "
                f"\"Admin sozlamalari\" -> \"{CARDS_KEY}\" ga kartalarni kiriting, "
                f"aks holda o'quvchi to'lay olmaydi."
            ))
