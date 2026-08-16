"""
Darslardan test savollari generatsiya qiladi (QORALAMA).

    python manage.py generate_quizzes --category python --limit 5
    python manage.py generate_quizzes --lesson-id 42 --questions 8
    python manage.py generate_quizzes --notes-dir ./dars_matnlari --category django

DIQQAT — MATN YETARLI BO'LMASA ISHLAMAYDI
=========================================
Model faqat unga berilgan matndan savol yoza oladi. Bu platformada
darslarning asosiy mazmuni VIDEODA, `theory` maydonida esa ko'pincha
bir necha so'z (yoki "Theory here") turibdi. Shunday darsdan generatsiya
qilinsa model sarlavhadan taxmin qilib, mavzuga umumiy — lekin darsga
mos kelmaydigan — savollar yozadi. O'quvchi videoda ko'rmagan narsasidan
imtihon topshirardi.

Shuning uchun buyruq matni `--min-theory` dan qisqa darslarni O'TKAZIB
YUBORADI va oxirida ular ro'yxatini ko'rsatadi. Uch yo'l bor:

  1. `theory` maydonini admin panelda to'ldiring (eng yaxshisi);
  2. `--notes-dir` bilan har dars uchun matn fayli bering —
     `<dars_id>.txt` yoki `<dars_id>.md`. Video transkripti, dars
     konspekti yoki slaydlar matni bo'lishi mumkin;
  3. `--allow-thin` bilan majburlang — lekin natija sifatsiz bo'ladi
     va uni qatorma-qator tekshirib chiqishga tayyor bo'ling.

NATIJA HAR DOIM QORALAMA
========================
Yaratilgan test `is_published=False` bilan saqlanadi — o'quvchi uni
ko'rmaydi. Admin panelda o'qib chiqib, "Nashr qilish" amali bilan
ochasiz. Tekshirilmagan savol o'quvchini chalg'itadi va sertifikatni
ma'nosiz qiladi.
"""

import json
import re
import textwrap
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Category, Choice, Lesson, Question, Quiz

#: Nazariya shundan qisqa bo'lsa dars o'tkazib yuboriladi
DEFAULT_MIN_THEORY = 200

#: Bitta testda nechta savol
DEFAULT_QUESTIONS = 5

#: Har savolda nechta variant
DEFAULT_CHOICES = 4

#: Bir yurishda nechta dars (xarajat nazorati)
DEFAULT_LIMIT = 10

#: Javob uzunligi. Savollar + variantlar + fikrlash shu chegara ichida.
MAX_TOKENS = 8000


SYSTEM_PROMPT = """Sen dasturlash o'qituvchisisan va dars uchun nazorat testini tuzayapsan.

## Qat'iy qoidalar

Savollarni FAQAT senga berilgan dars matnidan tuzasan. Matnda yo'q
narsani so'ramaysan — o'quvchi darsda ko'rmagan savolga javob bera
olmaydi va bu testni ma'nosiz qiladi.

Har savolda ANIQ BITTA to'g'ri javob bo'ladi. Qolgan variantlar ishonarli
bo'lsin: mavzuga aloqador, lekin aniq noto'g'ri. "Hech biri" yoki
"Yuqoridagilarning hammasi" kabi variantlar ishlatma.

Variantlar bir-biriga o'xshamasin va uzunligi taxminan teng bo'lsin —
eng uzun variant to'g'ri javob degan naqsh paydo bo'lmasin.

Savol matnining o'zida javob yashiringan bo'lmasin.

## Til va uslub

O'zbek tilida, lotin alifbosida yozasan. Texnik atamalarni tarjima
qilmaysan (masalan "funksiya", "o'zgaruvchi" — lekin `for`, `def`,
`class` kabi kalit so'zlar o'z holicha qoladi).

Savollar bir xil qiyinlikda bo'lmasin: bir qismi ta'rifni, bir qismi
kodning natijasini, bir qismi qachon nima ishlatilishini tekshirsin.

## Yetarli material bo'lmasa

Berilgan matn savol tuzish uchun juda qisqa yoki mazmunsiz bo'lsa,
o'ylab topmaysan — `questions` ro'yxatini bo'sh qaytarasan."""


# Model javobining shakli KAFOLATLANADI: struktura sxema bilan
# cheklanadi, shuning uchun "JSON qaytar" deb yozib, keyin uni
# tahlil qilishga urinish kerak emas.
def response_schema(n_questions: int, n_choices: int) -> dict:
    return {
        'type': 'object',
        'properties': {
            'questions': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'text': {'type': 'string'},
                        'choices': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'text': {'type': 'string'},
                                    'is_correct': {'type': 'boolean'},
                                },
                                'required': ['text', 'is_correct'],
                                'additionalProperties': False,
                            },
                        },
                    },
                    'required': ['text', 'choices'],
                    'additionalProperties': False,
                },
            },
        },
        'required': ['questions'],
        'additionalProperties': False,
    }


class Command(BaseCommand):
    help = "Darslardan QORALAMA test savollari generatsiya qiladi"

    def add_arguments(self, parser):
        target = parser.add_argument_group("Qaysi darslar")
        target.add_argument('--category', help="Yo'nalish slug'i (python, django, react, javascript)")
        target.add_argument('--lesson-id', type=int, action='append', dest='lesson_ids',
                            help="Aniq dars (bir necha marta berilishi mumkin)")
        target.add_argument('--limit', type=int, default=DEFAULT_LIMIT,
                            help=f"Bir yurishda nechta dars (standart {DEFAULT_LIMIT})")
        target.add_argument('--overwrite', action='store_true',
                            help="Testi bor darslarni ham qayta yozadi")

        content = parser.add_argument_group("Kontent")
        content.add_argument('--notes-dir',
                             help="Dars matnlari papkasi: <dars_id>.txt yoki <dars_id>.md")
        content.add_argument('--min-theory', type=int, default=DEFAULT_MIN_THEORY,
                             help=f"Matnning eng kam uzunligi (standart {DEFAULT_MIN_THEORY} belgi)")
        content.add_argument('--allow-thin', action='store_true',
                             help="Qisqa matnli darslarni ham majburlab generatsiya qiladi")

        shape = parser.add_argument_group("Test shakli")
        shape.add_argument('--questions', type=int, default=DEFAULT_QUESTIONS,
                           help=f"Nechta savol (standart {DEFAULT_QUESTIONS})")
        shape.add_argument('--choices', type=int, default=DEFAULT_CHOICES,
                           help=f"Har savolda nechta variant (standart {DEFAULT_CHOICES})")
        shape.add_argument('--time-limit', type=int, default=20,
                           help="Testga beriladigan vaqt, daqiqada")

        misc = parser.add_argument_group("Boshqa")
        misc.add_argument('--model', help="Model (standart sozlamalardan)")
        misc.add_argument('--dry-run', action='store_true',
                          help="Hech narsa saqlamaydi, faqat ko'rsatadi")

    # ----------------------------------------------------------------- #

    def handle(self, *args, **options):
        self.opts = options

        if not getattr(settings, 'ANTHROPIC_API_KEY', ''):
            raise CommandError(
                "ANTHROPIC_API_KEY sozlanmagan. .env ga qo'shing "
                "(DEPLOY.md 10-bo'lim)."
            )

        if options['questions'] < 1 or options['questions'] > 20:
            raise CommandError("--questions 1 dan 20 gacha bo'lishi kerak")
        if options['choices'] < 2 or options['choices'] > 6:
            raise CommandError("--choices 2 dan 6 gacha bo'lishi kerak")

        self.notes_dir = None
        if options['notes_dir']:
            self.notes_dir = Path(options['notes_dir'])
            if not self.notes_dir.is_dir():
                raise CommandError(f"Papka topilmadi: {self.notes_dir}")

        lessons = self._select_lessons()
        if not lessons:
            self.stdout.write(self.style.WARNING("Mos dars topilmadi."))
            return

        ready, thin = self._split_by_content(lessons)

        self.stdout.write(f"Tanlangan darslar : {len(lessons)}")
        self.stdout.write(f"Matni yetarli     : {len(ready)}")
        self.stdout.write(f"Matni qisqa       : {len(thin)}")

        if thin and not options['allow_thin']:
            self._report_thin(thin)

        targets = ready if not options['allow_thin'] else lessons
        targets = targets[: options['limit']]

        if not targets:
            self.stdout.write(self.style.ERROR(
                "\nGeneratsiya qilinadigan dars qolmadi. Yuqoridagi izohga qarang."
            ))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{len(targets)} ta dars uchun generatsiya boshlanmoqda...\n"
        ))

        stats = {'ok': 0, 'skipped': 0, 'failed': 0, 'in_tok': 0, 'out_tok': 0}

        for lesson in targets:
            self._process(lesson, stats)

        self._summary(stats)

    # ----------------------------------------------------------------- #
    # Darslarni tanlash
    # ----------------------------------------------------------------- #

    def _select_lessons(self):
        qs = Lesson.objects.select_related('module__category').order_by(
            'module__category__slug', 'module__order', 'order', 'id'
        )

        if self.opts['lesson_ids']:
            qs = qs.filter(id__in=self.opts['lesson_ids'])
            found = {l.id for l in qs}
            missing = set(self.opts['lesson_ids']) - found
            if missing:
                raise CommandError(f"Bunday dars yo'q: {sorted(missing)}")

        if self.opts['category']:
            slug = self.opts['category'].lower()
            if not Category.objects.filter(slug__iexact=slug).exists():
                available = ", ".join(Category.objects.values_list('slug', flat=True))
                raise CommandError(f"Bunday yo'nalish yo'q: {slug}. Mavjud: {available}")
            qs = qs.filter(module__category__slug__iexact=slug)

        if not self.opts['overwrite']:
            qs = qs.filter(quiz__isnull=True)

        return list(qs)

    def _lesson_text(self, lesson) -> str:
        """
        Dars matni. Fayl bo'lsa u ustunlik qiladi — o'qituvchi bergan
        transkript `theory` dan har doim boyroq.
        """
        if self.notes_dir:
            for ext in ('.txt', '.md'):
                path = self.notes_dir / f"{lesson.id}{ext}"
                if path.is_file():
                    return path.read_text(encoding='utf-8').strip()

        parts = []
        theory = (lesson.theory or '').strip()
        if theory:
            # `theory` HTML saqlashi mumkin — teglarni tozalaymiz
            parts.append(re.sub(r'<[^>]+>', ' ', theory))
        code = (lesson.practice_code or '').strip()
        if code:
            parts.append("Darsdagi kod namunasi:\n" + code)
        return "\n\n".join(parts).strip()

    def _split_by_content(self, lessons):
        ready, thin = [], []
        for lesson in lessons:
            text = self._lesson_text(lesson)
            (ready if len(text) >= self.opts['min_theory'] else thin).append((lesson, text))
        return ready, thin

    def _report_thin(self, thin):
        self.stdout.write(self.style.WARNING(
            f"\n{len(thin)} ta darsning matni {self.opts['min_theory']} belgidan qisqa "
            f"— ular O'TKAZIB YUBORILDI.\n"
        ))
        for lesson, text in thin[:15]:
            self.stdout.write(
                f"  #{lesson.id:<4} [{lesson.module.category.slug:10}] "
                f"{lesson.title[:40]:<42} {len(text):>4} belgi"
            )
        if len(thin) > 15:
            self.stdout.write(f"  ... yana {len(thin) - 15} ta")

        self.stdout.write(
            "\n  Model faqat berilgan matndan savol yoza oladi. Bu darslarning\n"
            "  mazmuni videoda bo'lgani uchun matn yetarli emas — sarlavhadan\n"
            "  taxmin qilingan savollar darsga mos kelmaydi.\n"
            "\n  Yechim (biridan foydalaning):\n"
            "    1. Admin panelda dars 'Nazariya' maydonini to'ldiring\n"
            "    2. --notes-dir ./papka  — har dars uchun <dars_id>.txt fayl\n"
            "       (video transkripti, konspekt yoki slayd matni)\n"
            "    3. --allow-thin        — majburlash, lekin sifat past bo'ladi\n"
        )

    # ----------------------------------------------------------------- #
    # Generatsiya
    # ----------------------------------------------------------------- #

    def _process(self, item, stats):
        lesson, text = item if isinstance(item, tuple) else (item, self._lesson_text(item))

        label = f"#{lesson.id} [{lesson.module.category.slug}] {lesson.title[:45]}"
        self.stdout.write(f"  {label} ... ", ending='')
        self.stdout.flush()

        try:
            payload, usage = self._ask_model(lesson, text)
        except Exception as exc:
            self.stdout.write(self.style.ERROR("XATO"))
            self.stdout.write(self.style.ERROR(f"      {exc}"))
            stats['failed'] += 1
            return

        stats['in_tok'] += usage[0]
        stats['out_tok'] += usage[1]

        questions = payload.get('questions') or []
        problems = self._validate(questions)

        if not questions:
            self.stdout.write(self.style.WARNING("BO'SH"))
            self.stdout.write(
                "      Model yetarli material topmadi — matnni boyiting."
            )
            stats['skipped'] += 1
            return

        if problems:
            self.stdout.write(self.style.ERROR("YAROQSIZ"))
            for p in problems[:3]:
                self.stdout.write(self.style.ERROR(f"      {p}"))
            stats['failed'] += 1
            return

        if self.opts['dry_run']:
            self.stdout.write(self.style.SUCCESS(f"{len(questions)} savol (dry-run)"))
            self._preview(questions)
            stats['ok'] += 1
            return

        self._save(lesson, questions)
        self.stdout.write(self.style.SUCCESS(f"{len(questions)} savol -> qoralama"))
        stats['ok'] += 1

    def _ask_model(self, lesson, text):
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        n_q = self.opts['questions']
        n_c = self.opts['choices']

        prompt = (
            f"Yo'nalish: {lesson.module.category.name}\n"
            f"Dars: {lesson.title}\n\n"
            f"--- DARS MATNI ---\n{text}\n--- MATN TUGADI ---\n\n"
            f"Shu matn asosida {n_q} ta test savoli tuz. "
            f"Har savolda {n_c} ta variant bo'lsin, ulardan aniq bittasi to'g'ri.\n\n"
            f"Matn savol tuzish uchun yetarli bo'lmasa, bo'sh ro'yxat qaytar."
        )

        response = client.messages.create(
            model=self.opts['model'] or settings.ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            # Tizim ko'rsatmasi barcha darslar uchun bir xil — keshlanadi
            system=[{
                'type': 'text',
                'text': SYSTEM_PROMPT,
                'cache_control': {'type': 'ephemeral'},
            }],
            # Javob shakli SXEMA bilan kafolatlanadi — "JSON qaytar" deb
            # yozib, keyin uni tahlil qilishga urinish kerak emas.
            output_config={
                'format': {
                    'type': 'json_schema',
                    'schema': response_schema(n_q, n_c),
                },
                'effort': 'medium',
            },
            messages=[{'role': 'user', 'content': prompt}],
        )

        if response.stop_reason == 'refusal':
            raise RuntimeError("Model so'rovni rad etdi")

        raw = "".join(b.text for b in response.content if b.type == 'text')
        if not raw.strip():
            raise RuntimeError("Model bo'sh javob qaytardi")

        return json.loads(raw), (response.usage.input_tokens, response.usage.output_tokens)

    # ----------------------------------------------------------------- #
    # Tekshirish
    # ----------------------------------------------------------------- #

    def _validate(self, questions):
        """
        Sxema shaklni kafolatlaydi, lekin MA'NONI emas: to'g'ri javoblar
        soni, takroriy variantlar va bo'sh matn baribir tekshiriladi.
        Yaroqsiz test saqlanmasligi kerak — admin uni qo'lda tuzatishdan
        ko'ra qayta generatsiya qilgani osonroq.
        """
        problems = []
        n_c = self.opts['choices']

        for i, q in enumerate(questions, 1):
            text = (q.get('text') or '').strip()
            if not text:
                problems.append(f"{i}-savol matni bo'sh")
                continue

            choices = q.get('choices') or []
            if len(choices) != n_c:
                problems.append(f"{i}-savolda {len(choices)} variant ({n_c} kerak)")
                continue

            texts = [(c.get('text') or '').strip() for c in choices]
            if any(not t for t in texts):
                problems.append(f"{i}-savolda bo'sh variant bor")
            if len(set(t.lower() for t in texts)) != len(texts):
                problems.append(f"{i}-savolda takroriy variant bor")

            correct = sum(1 for c in choices if c.get('is_correct'))
            if correct != 1:
                problems.append(f"{i}-savolda {correct} ta to'g'ri javob (1 kerak)")

        return problems

    # ----------------------------------------------------------------- #
    # Saqlash va ko'rsatish
    # ----------------------------------------------------------------- #

    @transaction.atomic
    def _save(self, lesson, questions):
        # Qayta yozishda eski test butunlay o'chiriladi — savollar
        # aralashib ketmasin.
        Quiz.objects.filter(lesson=lesson).delete()

        quiz = Quiz.objects.create(
            lesson=lesson,
            title=f"{lesson.title} — nazorat testi",
            time_limit=self.opts['time_limit'],
            # QORALAMA: tekshirilmagan savol o'quvchiga ko'rinmasligi kerak
            is_published=False,
            is_generated=True,
        )

        for q in questions:
            question = Question.objects.create(quiz=quiz, text=q['text'].strip())
            Choice.objects.bulk_create([
                Choice(
                    question=question,
                    text=c['text'].strip()[:255],
                    is_correct=bool(c.get('is_correct')),
                )
                for c in q['choices']
            ])

    def _preview(self, questions):
        # Belgilar ATAYLAB ASCII: Windows konsoli cp1251 da ishlaydi va
        # unda "✓" (U+2713) umuman yo'q — buyruq UnicodeEncodeError bilan
        # yiqilardi. Test runner chiqishni StringIO ga olgani uchun buni
        # testda sezib bo'lmaydi.
        for i, q in enumerate(questions, 1):
            self.stdout.write(f"\n      {i}. {textwrap.shorten(q['text'], 90)}")
            for c in q['choices']:
                mark = self.style.SUCCESS("[to'g'ri]") if c.get('is_correct') else "         "
                self.stdout.write(f"       {mark} {textwrap.shorten(c['text'], 80)}")
        self.stdout.write("")

    def _summary(self, stats):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Natija"))
        self.stdout.write(f"  Yaratildi : {stats['ok']}")
        self.stdout.write(f"  O'tkazildi: {stats['skipped']}")
        self.stdout.write(f"  Xato      : {stats['failed']}")
        self.stdout.write(
            f"  Tokenlar  : {stats['in_tok']:,} kirish / {stats['out_tok']:,} chiqish"
        )

        if stats['ok'] and not self.opts['dry_run']:
            self.stdout.write(self.style.WARNING(
                "\n  Testlar QORALAMA holatda — o'quvchi ularni hali ko'rmaydi.\n"
                "  Admin panel -> Testlar -> o'qib chiqing -> \"Nashr qilish\" amali.\n"
                "\n  Har savolni tekshiring: model matnni noto'g'ri tushungan\n"
                "  bo'lishi yoki to'g'ri javobni xato belgilagan bo'lishi mumkin."
            ))
