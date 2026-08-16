"""
Topshiriq tavsiflarini HTML dan oddiy matnga o'tkazadi.

    python manage.py convert_challenge_html --dry-run
    python manage.py convert_challenge_html

NEGA KERAK: `Challenge.description` eskidan HTML sifatida saqlangan va
eski shablon uni `|safe` bilan chiqarardi. Dars matni esa oddiy matn
(`core/richtext.py`). Ikki xil format bir xil turdagi kontent uchun —
bu aynan shu loyiha qochadigan "ikki manba" muammosi: qaysi biri
to'g'ri ekani vaqt o'tib bilinmay qoladi.

XAVFSIZLIK: buyruq HTML BO'LMAGAN tavsiflarga TEGMAYDI, ya'ni qayta
ishga tushirilishi xavfsiz. Avval `--dry-run` bilan natijani ko'ring.

QO'LLAB-QUVVATLANADIGAN TEGLAR — bazada aslida uchraydiganlari:
`h3`, `p`, `b`/`strong`, `code`, `ul`/`li`, `br`. Boshqasi uchrasa
buyruq TO'XTAYDI va qaysi teg ekanini aytadi — jimgina ma'lumot
yo'qotgandan ko'ra to'xtagani yaxshi.
"""

import re

from django.core.management.base import BaseCommand, CommandError

from core.models import Challenge

#: Aylantirish qoidalari, TARTIB BILAN qo'llanadi
RULES = [
    (r'<h[1-6][^>]*>(.*?)</h[1-6]>', r'\n## \1\n'),
    (r'<li[^>]*>(.*?)</li>', r'\n- \1'),
    (r'</?ul[^>]*>', '\n'),
    (r'</?ol[^>]*>', '\n'),
    (r'<code[^>]*>(.*?)</code>', r'`\1`'),
    (r'<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>', r'**\1**'),
    (r'<(?:i|em)[^>]*>(.*?)</(?:i|em)>', r'*\1*'),
    (r'<br\s*/?>', '\n'),
    (r'<p[^>]*>', '\n\n'),
    (r'</p>', '\n'),
]

#: Aylantirilgandan keyin qolishi mumkin bo'lgan teglar yo'q —
#: qolgani noma'lum deb hisoblanadi
KNOWN_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'b', 'strong',
              'i', 'em', 'code', 'ul', 'ol', 'li', 'br'}

ENTITIES = [
    ('&nbsp;', ' '), ('&amp;', '&'), ('&lt;', '<'),
    ('&gt;', '>'), ('&quot;', '"'), ('&#39;', "'"),
]


def has_html(text: str) -> bool:
    return bool(re.search(r'<[a-z][a-z0-9]*[^>]*>', (text or '').lower()))


def unknown_tags(text: str) -> set:
    found = set(re.findall(r'</?([a-z][a-z0-9]*)', (text or '').lower()))
    return found - KNOWN_TAGS


def convert(html: str) -> str:
    """HTML ni `core/richtext.py` tushunadigan oddiy matnga aylantiradi."""
    text = html or ''

    for pattern, replacement in RULES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE | re.DOTALL)

    for entity, char in ENTITIES:
        text = text.replace(entity, char)

    # Uch va undan ortiq bo'sh qatorni ikkitaga tushiramiz —
    # `richtext` uchun ikkitasi yetarli
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Qator oxiridagi bo'shliqlar
    text = '\n'.join(line.rstrip() for line in text.split('\n'))

    return text.strip()


class Command(BaseCommand):
    help = "Topshiriq tavsiflarini HTML dan oddiy matnga o'tkazadi"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help="Bazaga tegmaydi, faqat natijani ko'rsatadi")

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        challenges = list(Challenge.objects.all().order_by('order'))

        # AVVAL HAMMASINI TEKSHIRAMIZ, keyin yozamiz: yarmi
        # aylantirilib, yarmi qolib ketmasin.
        problems = []
        for challenge in challenges:
            if not has_html(challenge.description):
                continue
            unknown = unknown_tags(challenge.description)
            if unknown:
                problems.append((challenge, unknown))

        if problems:
            for challenge, unknown in problems:
                self.stderr.write(
                    self.style.ERROR(
                        f"  #{challenge.pk} «{challenge.title}»: "
                        f"noma'lum teg — {', '.join(sorted(unknown))}"
                    )
                )
            raise CommandError(
                "Noma'lum teglar topildi. Ular qo'lda tuzatilsin yoki "
                "RULES ga qo'shilsin — jimgina yo'qotib yubormaslik uchun to'xtatildi."
            )

        converted = skipped = 0

        for challenge in challenges:
            if not has_html(challenge.description):
                self.stdout.write(f"  o'tkazildi  #{challenge.pk} {challenge.title}")
                skipped += 1
                continue

            new_text = convert(challenge.description)

            self.stdout.write(f"\n  #{challenge.pk} {challenge.title}")
            self.stdout.write(self.style.WARNING(f"      eski: {challenge.description[:90]}"))
            self.stdout.write(self.style.SUCCESS(f"      yangi: {new_text[:90]!r}"))

            if not dry_run:
                challenge.description = new_text
                challenge.save(update_fields=['description'])
            converted += 1

        self.stdout.write("\nNatija")
        self.stdout.write(f"  Aylantirildi : {converted}")
        self.stdout.write(f"  Tegilmadi    : {skipped}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\ndry-run: bazaga hech narsa yozilmadi."))
