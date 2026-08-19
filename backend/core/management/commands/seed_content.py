"""
Dars mazmunini bo'sh bazaga yuklaydi.

    python manage.py seed_content            # bo'sh bo'lsa yuklaydi
    python manage.py seed_content --dry-run  # nima bo'lishini ko'rsatadi
    python manage.py seed_content --force    # borini ustiga yozadi

NEGA KERAK

Railway'ga birinchi deployda faqat `migrate` ishlaydi va baza BO'SH
qoladi: jadvallar bor, mazmun yo'q. Natijada sayt ochiladi-yu, kurslar,
loyihalar va muharrir bo'limlari bo'm-bo'sh ko'rinadi. Mazmunni qo'lda
qayta kiritish 83 ta dars va 1000 dan ortiq test varianti degani.

Shuning uchun mazmun `core/fixtures/content.json` da repozitoriyda
yotadi va shu buyruq uni bazaga quyadi. Buyruq deploy paytida ishga
tushadi (`railway.json` dagi startCommand).

NIMA YUKLANADI: bo'lim, modul, dars, dars rasmi, test, savol, variant,
loyiha, muharrir topshirig'i va tarif.

NIMA YUKLANMAYDI: foydalanuvchilar, obunalar, to'lovlar, sertifikatlar
va KARTA REKVIZITLARI. Ular shaxsiy yoki maxfiy — repozitoriyda
yotishi mumkin emas. Karta panel orqali, joyida kiritiladi.

QAYTA ISHGA TUSHIRISH XAVFSIZ

Standart holatda buyruq bazada bo'lim BORLIGINI tekshiradi va bor
bo'lsa hech narsaga tegmasdan chiqadi. Bu MUHIM: startCommand har
deployda ishlaydi va tekshiruvsiz fixture adminning panel orqali
kiritgan o'zgarishlarini har safar bosib ketardi.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.models import Category

#: Fixture `core/fixtures/` ichida — Django uni nomi bo'yicha topadi.
FIXTURE = 'content.json'


class Command(BaseCommand):
    help = "Dars mazmunini (kurslar, loyihalar, topshiriqlar) bazaga yuklaydi"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help="Hech narsa yozmaydi, faqat holatni aytadi")
        parser.add_argument(
            '--force', action='store_true',
            help=(
                "Bazada mazmun bo'lsa ham yuklaydi. Bir xil ID li yozuvlar "
                "USTIGA YOZILADI — panel orqali kiritilgan o'zgarishlar yo'qoladi."
            ),
        )

    def handle(self, *args, **options):
        existing = Category.objects.count()

        if existing and not options['force']:
            self.stdout.write(
                f"Bazada allaqachon {existing} ta bo'lim bor — mazmun yuklanmadi.\n"
                "Ataylab ustiga yozmoqchi bo'lsangiz: --force"
            )
            return

        if options['dry_run']:
            self.stdout.write(f"dry-run: `{FIXTURE}` yuklanardi (bo'limlar: {existing}).")
            return

        # XATO DEPLOYNI O'LDIRMASLIGI KERAK.
        #
        # Bu buyruq `startCommand` zanjirida `gunicorn` dan OLDIN
        # turadi. Xato yuqoriga chiqsa, zanjir uzilardi va server
        # umuman ko'tarilmasdi — ya'ni mazmun yuklanmagani butun
        # saytni yiqitardi. Mazmunsiz sayt esa ishlaydi, shunchaki
        # bo'sh. Shuning uchun xato faqat LOGGA yoziladi.
        try:
            call_command('loaddata', FIXTURE, verbosity=options['verbosity'])
        except Exception as exc:
            self.stderr.write(self.style.ERROR(
                f"Mazmunni yuklab bo'lmadi: {exc}\n"
                "Server baribir ishga tushadi, lekin bo'limlar bo'sh bo'ladi."
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Mazmun yuklandi: {Category.objects.count()} ta bo'lim."
        ))
