"""
Navbatda qolgan panel xabarlarini yuboradi.

NEGA KERAK: panel tugmasi yuborishni boshlaydi, lekin katta ro'yxatni
bitta HTTP so'rovida tugatib bo'lmaydi (gunicorn uzib qo'yadi). Panel
o'ziga ajratilgan vaqt tugagach to'xtaydi va qolgani navbatda qoladi.
Shu buyruq o'sha qoldiqni yuboradi.

QANDAY ISHLATILADI: kunlik vazifalar bilan birga, lekin tez-tez —
masalan har 5 daqiqada:

    */5 * * * * cd /srv/nexus && /srv/nexus/venv/bin/python manage.py send_panel_messages

TAKROR YUBORMAYDI: har bir oluvchi uchun alohida qator bor va u
`(xabar, foydalanuvchi)` bo'yicha unique. Buyruq bir vaqtda ikki marta
ishga tushib qolsa ham bir odam bitta xabarni ikki marta olmaydi.
"""

from django.core.management.base import BaseCommand

from panel import messaging
from panel.models import MessageStatus, PanelMessage


class Command(BaseCommand):
    help = "Navbatda qolgan panel xabarlarini Telegramga yuboradi"

    def add_arguments(self, parser):
        parser.add_argument(
            '--budget',
            type=int,
            default=0,
            help=(
                "Yuborishga ajratiladigan vaqt (soniya). 0 = cheklovsiz. "
                "Cron tez-tez ishlasa, oldingi yurish tugamasdan yangisi "
                "boshlanmasligi uchun cheklab qo'yish foydali."
            ),
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Hech narsa yubormaydi, faqat navbatni ko'rsatadi",
        )

    def handle(self, *args, **options):
        pending = PanelMessage.objects.filter(status=MessageStatus.PENDING).order_by('created_at')

        if not pending.exists():
            self.stdout.write("Navbatda xabar yo'q.")
            return

        self.stdout.write(f"Navbatda {pending.count()} ta xabar:")
        for message in pending:
            self.stdout.write(
                f"  #{message.pk} {message.get_audience_display()} — "
                f"{message.delivered}/{message.total} yuborilgan, "
                f"{message.pending_count} ta qoldi"
            )

        if options['dry_run']:
            self.stdout.write(self.style.WARNING("\ndry-run: hech narsa yuborilmadi."))
            return

        if not messaging.telegram.is_configured():
            # ATAYLAB xato bilan tugaydi: cron jimgina "hammasi joyida"
            # deb o'tib ketmasin, xat yozib bersin.
            self.stderr.write(
                self.style.ERROR(
                    "Telegram bot sozlanmagan (TELEGRAM_BOT_TOKEN). Yuborilmadi."
                )
            )
            raise SystemExit(1)

        budget = options['budget'] or None
        result = messaging.deliver_all_pending(budget_seconds=budget)

        self.stdout.write("")
        self.stdout.write(f"  Xabarlar  : {result['messages']}")
        self.stdout.write(self.style.SUCCESS(f"  Yuborildi : {result['sent']}"))
        if result['failed']:
            self.stdout.write(self.style.WARNING(f"  Xato      : {result['failed']}"))

        left = sum(m.pending_count for m in PanelMessage.objects.filter(status=MessageStatus.PENDING))
        if left:
            self.stdout.write(f"  Navbatda  : {left} (keyingi yurishda yuboriladi)")
