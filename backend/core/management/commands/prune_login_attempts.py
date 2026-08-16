"""
Eski login urinishlari yozuvlarini o'chiradi.

Jadval har bir urinishga bitta qator yozadi — hujum paytida bu tez o'sadi.
Cheklov faqat oxirgi 15 daqiqani qaraydi, lekin jurnal tergov uchun bir
oy saqlanadi (`lockout.RETENTION`).

cron da kuniga bir marta:
    python manage.py prune_login_attempts
"""

from django.core.management.base import BaseCommand

from core import lockout
from core.models import LoginAttempt


class Command(BaseCommand):
    help = "30 kundan oshgan login urinishlari yozuvlarini o'chiradi"

    def handle(self, *args, **options):
        before = LoginAttempt.objects.count()
        removed = lockout.prune_old()
        self.stdout.write(self.style.SUCCESS(
            f"O'chirildi: {removed} ta ({before} -> {before - removed})"
        ))
