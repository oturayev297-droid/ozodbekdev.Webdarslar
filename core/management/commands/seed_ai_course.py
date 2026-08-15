"""
«Sun'iy intellekt va prompt engineering» kursini bazaga yozadi.

    python manage.py seed_ai_course

QAYTA ISHGA TUSHIRISH XAVFSIZ (idempotent): mavjud yozuvlar
YANGILANADI, ikkinchi nusxa yaratilmaydi. Darslar `(modul, sarlavha)`
bo'yicha topiladi.

NIMA SAQLANIB QOLADI: o'quvchilarning o'zlashtirishi
(`UserProgress`) va test natijalari darslar `id` si o'zgarmagani
uchun joyida qoladi. Shu sabab dars O'CHIRILIB QAYTA YARATILMAYDI —
u yangilanadi.

TESTLAR: savollar har safar QAYTA yoziladi (avval o'chiriladi).
Sababi — savol matnini o'zgartirganda eskisi yonida qolib ketmasligi
kerak. `QuizResult` esa testga bog'langan, savolga emas, shuning
uchun o'tgan natijalar yo'qolmaydi.
"""

import textwrap

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core import diagrams
from core.models import Category, Choice, Lesson, LessonImage, Module, Question, Quiz

from ._ai_course_data import CATEGORY, MODULES


class Command(BaseCommand):
    help = "«Sun'iy intellekt» kursini yaratadi yoki yangilaydi"

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-images',
            action='store_true',
            help="Sxemalarni chizmaydi (Pillow shrifti muammo bersa yoki tezroq kerak bo'lsa)",
        )
        parser.add_argument(
            '--publish-quizzes',
            action='store_true',
            help=(
                "Testlarni darhol nashr qiladi. Standart holatda ular "
                "QORALAMA bo'lib qoladi — savollarni o'qib chiqib, "
                "panelda o'zingiz nashr qilasiz."
            ),
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Bazaga tegmaydi, faqat nima qilinishini ko'rsatadi",
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.no_images = options['no_images']
        self.publish = options['publish_quizzes']

        if self.dry_run:
            self.stdout.write(self.style.WARNING("dry-run: bazaga hech narsa yozilmaydi\n"))

        stats = {'lessons': 0, 'updated': 0, 'quizzes': 0, 'questions': 0, 'images': 0}

        try:
            if self.dry_run:
                self._preview(stats)
            else:
                with transaction.atomic():
                    self._run(stats)
        except Exception as exc:
            raise CommandError(f"Kurs yozilmadi: {exc}") from exc

        self._report(stats)

    # ────────────────────────────── Asosiy ish ──────────────────────────────

    def _run(self, stats):
        category, created = Category.objects.update_or_create(
            slug=CATEGORY['slug'],
            defaults={'name': CATEGORY['name'], 'description': CATEGORY['description']},
        )
        self.stdout.write(
            f"Bo'lim: {category.name} "
            + self.style.SUCCESS("(yaratildi)" if created else "(yangilandi)")
        )

        for module_data in MODULES:
            module, _ = Module.objects.update_or_create(
                category=category,
                title=module_data['title'],
                defaults={'order': module_data['order']},
            )
            self.stdout.write(f"\n  {module.order}. {module.title}")

            for index, lesson_data in enumerate(module_data['lessons'], 1):
                self._save_lesson(module, lesson_data, index, stats)

    def _save_lesson(self, module, data, order, stats):
        theory = textwrap.dedent(data['theory']).strip()

        lesson, created = Lesson.objects.update_or_create(
            module=module,
            title=data['title'],
            defaults={
                'theory': theory,
                'order': order,
                'is_free': data.get('free', False),
                'practice_code': data.get('practice_code', ''),
            },
        )

        stats['lessons' if created else 'updated'] += 1
        mark = "yangi" if created else "yangilandi"
        access = self.style.SUCCESS("bepul") if lesson.is_free else "obuna"
        self.stdout.write(
            f"     {order}. {lesson.title[:52]:<52} {len(theory):>5} belgi  {access}  ({mark})"
        )

        if data.get('image') and not self.no_images:
            self._save_image(lesson, data, stats)

        if data.get('quiz'):
            self._save_quiz(lesson, data['quiz'], stats)

    def _save_image(self, lesson, data, stats):
        """
        Sxemani chizadi va darsga biriktiradi.

        ESKISI O'CHIRILADI: aks holda buyruq har ishga tushganda bir xil
        rasm yana bir marta qo'shilib, dars oxirida bir necha nusxa
        turib qolardi.
        """
        name = data['image']

        for old in lesson.images.all():
            old.image.delete(save=False)
            old.delete()

        try:
            png = diagrams.render(name)
        except Exception as exc:
            # Rasm chizilmasa DARS BARIBIR SAQLANADI. Sxema — foydali
            # qo'shimcha, lekin matnsiz qolishdan ko'ra rasmsiz qolgan
            # yaxshi.
            self.stderr.write(self.style.WARNING(f"        sxema chizilmadi ({name}): {exc}"))
            return

        image = LessonImage(
            lesson=lesson,
            caption=data.get('image_caption', ''),
            alt_text=data.get('image_alt', data.get('image_caption', '')),
            order=1,
        )
        image.image.save(f"{lesson.pk}_{name}.png", ContentFile(png), save=False)
        image.save()

        stats['images'] += 1
        self.stdout.write(f"        sxema: {name} ({len(png):,} bayt)")

    def _save_quiz(self, lesson, data, stats):
        quiz, _ = Quiz.objects.update_or_create(
            lesson=lesson,
            defaults={
                'title': data['title'],
                'time_limit': data.get('time_limit', 10),
                'is_published': self.publish,
                # Bu savollarni model emas, odam yozgan — bayroq
                # `generate_quizzes` chiqargan testlar uchun.
                'is_generated': False,
            },
        )

        # Savollar QAYTA yoziladi: matn tuzatilganda eskisi yonida
        # qolib ketmasin. Natijalar testga bog'langan, savolga emas.
        quiz.questions.all().delete()

        for question_data in data['questions']:
            question = Question.objects.create(quiz=quiz, text=question_data['text'])
            for text, is_correct in question_data['choices']:
                Choice.objects.create(question=question, text=text, is_correct=is_correct)
            stats['questions'] += 1

        stats['quizzes'] += 1
        state = self.style.SUCCESS("nashrda") if self.publish else "qoralama"
        self.stdout.write(
            f"        test: {len(data['questions'])} savol ({state})"
        )

    # ────────────────────────────── dry-run ──────────────────────────────

    def _preview(self, stats):
        self.stdout.write(f"Bo'lim: {CATEGORY['name']} ({CATEGORY['slug']})")
        for module_data in MODULES:
            self.stdout.write(f"\n  {module_data['order']}. {module_data['title']}")
            for order, lesson in enumerate(module_data['lessons'], 1):
                theory = textwrap.dedent(lesson['theory']).strip()
                quiz = lesson.get('quiz')
                access = "bepul" if lesson.get('free') else "obuna"
                self.stdout.write(
                    f"     {order}. {lesson['title'][:52]:<52} "
                    f"{len(theory):>5} belgi  {access}"
                )
                if lesson.get('image'):
                    self.stdout.write(f"        sxema: {lesson['image']}")
                    stats['images'] += 1
                if quiz:
                    self.stdout.write(f"        test: {len(quiz['questions'])} savol")
                    stats['quizzes'] += 1
                    stats['questions'] += len(quiz['questions'])
                stats['lessons'] += 1

    # ────────────────────────────── Natija ──────────────────────────────

    def _report(self, stats):
        self.stdout.write("\nNatija")
        self.stdout.write(f"  Yangi dars   : {stats['lessons']}")
        if stats['updated']:
            self.stdout.write(f"  Yangilandi   : {stats['updated']}")
        self.stdout.write(f"  Sxema        : {stats['images']}")
        self.stdout.write(f"  Test         : {stats['quizzes']}")
        self.stdout.write(f"  Savol        : {stats['questions']}")

        if self.dry_run:
            return

        if not self.publish:
            self.stdout.write(
                "\n" + self.style.WARNING(
                    "Testlar QORALAMA holatida. O'quvchi ularni ko'rmaydi.\n"
                    "Savollarni o'qib chiqing va /panel/testlar/ da nashr qiling."
                )
            )
