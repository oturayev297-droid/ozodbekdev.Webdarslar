"""
«Sun'iy intellekt» kursini yozuvchi buyruq testlari.

IKKI NARSA QO'RIQLANADI:

1. QAYTA ISHGA TUSHIRISH XAVFSIZLIGI. Buyruq serverda bir necha marta
   ishlatiladi (matn tuzatilganda). Ikkinchi yurish nusxa yaratsa yoki
   o'quvchilarning o'zlashtirishini o'chirib yuborsa — bu jimgina
   sodir bo'ladigan, lekin qaytarib bo'lmaydigan zarar.

2. SAVOLLARNING TO'G'RILIGI. Matn bu faylda qo'lda yozilgan, ya'ni
   xato ham qo'lda kiritiladi. Ikkita to'g'ri javobli savol testni
   ishonchsiz qiladi va sertifikatni ma'nosiz.
"""

import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from core.management.commands._ai_course_data import CATEGORY, MODULES
from core.models import Category, Choice, Lesson, LessonImage, Module, Question, Quiz


#: Sxemalar HAQIQIY `media/` papkasiga tushmasligi kerak — buyruq har
#: yurishda 8 ta PNG yozadi va ular test tugagach ham qolib ketardi.
TEST_MEDIA = tempfile.mkdtemp(prefix='nexus-test-media-')


def tearDownModule():
    shutil.rmtree(TEST_MEDIA, ignore_errors=True)


def run(*args):
    out = StringIO()
    call_command('seed_ai_course', *args, stdout=out, stderr=StringIO())
    return out.getvalue()


class ContentDataTests(TestCase):
    """
    Matnning o'zini tekshiradi — bazaga yozmasdan.

    Bu testlar sekin emas va buyruq umuman ishlamasa ham nima
    noto'g'ri ekanini aniq ko'rsatadi.
    """

    def _all_lessons(self):
        for module in MODULES:
            for lesson in module['lessons']:
                yield module, lesson

    def _all_questions(self):
        for _, lesson in self._all_lessons():
            quiz = lesson.get('quiz')
            if quiz:
                for question in quiz['questions']:
                    yield lesson, quiz, question

    def test_har_savolda_ROPPA_ROSA_bitta_togri_javob(self):
        for lesson, quiz, question in self._all_questions():
            correct = [text for text, ok in question['choices'] if ok]
            with self.subTest(savol=question['text'][:50]):
                self.assertEqual(
                    len(correct), 1,
                    f"«{quiz['title']}» testida to'g'ri javoblar soni {len(correct)}",
                )

    def test_variantlar_takrorlanmaydi(self):
        for lesson, quiz, question in self._all_questions():
            texts = [text for text, _ in question['choices']]
            with self.subTest(savol=question['text'][:50]):
                self.assertEqual(len(texts), len(set(texts)))

    def test_har_savolda_kamida_uchta_variant(self):
        """Ikkita variantli savol tanlov emas, tanga tashlash."""
        for lesson, quiz, question in self._all_questions():
            with self.subTest(savol=question['text'][:50]):
                self.assertGreaterEqual(len(question['choices']), 3)

    def test_bosh_variant_yoq(self):
        for lesson, quiz, question in self._all_questions():
            for text, _ in question['choices']:
                with self.subTest(savol=question['text'][:50]):
                    self.assertTrue(text.strip())

    def test_dars_matni_yetarli_uzunlikda(self):
        """
        200 belgi — `generate_quizzes` dagi chegara bilan bir xil.
        Undan qisqa matn dars sifatida ham arzimaydi.
        """
        for module, lesson in self._all_lessons():
            with self.subTest(dars=lesson['title']):
                self.assertGreater(len(lesson['theory'].strip()), 200)

    def test_dars_sarlavhalari_takrorlanmaydi(self):
        """
        Buyruq darsni `(modul, sarlavha)` bo'yicha topadi. Bir modulda
        ikkita bir xil sarlavha bo'lsa, ikkinchisi birinchisining
        ustiga yozilardi va bitta dars yo'qolardi.
        """
        for module in MODULES:
            titles = [lesson['title'] for lesson in module['lessons']]
            with self.subTest(modul=module['title']):
                self.assertEqual(len(titles), len(set(titles)))

    def test_kamida_bitta_bepul_dars_bor(self):
        """Bepul dars bo'lmasa odam nima sotib olayotganini ko'rmaydi."""
        free = [l for _, l in self._all_lessons() if l.get('free')]
        self.assertGreaterEqual(len(free), 1)

    def test_hamma_dars_bepul_EMAS(self):
        """Hammasi bepul bo'lsa kursning savdo qiymati qolmaydi."""
        paid = [l for _, l in self._all_lessons() if not l.get('free')]
        self.assertGreaterEqual(len(paid), 1)

    def test_sxema_nomlari_haqiqiy(self):
        from core import diagrams

        for module, lesson in self._all_lessons():
            name = lesson.get('image')
            if name:
                with self.subTest(dars=lesson['title']):
                    self.assertIn(name, diagrams.DIAGRAMS)


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class SeedCommandTests(TestCase):
    """Buyruqning bazadagi ta'siri."""

    def test_kurs_yoziladi(self):
        run('--no-images')

        category = Category.objects.get(slug=CATEGORY['slug'])
        self.assertEqual(Module.objects.filter(category=category).count(), len(MODULES))

        expected = sum(len(m['lessons']) for m in MODULES)
        self.assertEqual(Lesson.objects.filter(module__category=category).count(), expected)

    def test_testlar_QORALAMA_bolib_tushadi(self):
        """Savollar o'qib chiqilmaguncha o'quvchi ularni ko'rmasligi kerak."""
        run('--no-images')
        self.assertFalse(
            Quiz.objects.filter(lesson__module__category__slug='ai', is_published=True).exists()
        )

    def test_publish_bayrogi_nashr_qiladi(self):
        run('--no-images', '--publish-quizzes')
        self.assertFalse(
            Quiz.objects.filter(lesson__module__category__slug='ai', is_published=False).exists()
        )

    def test_model_generatsiya_qilgan_deb_belgilanmaydi(self):
        """Bu savollarni odam yozgan — bayroq `generate_quizzes` uchun."""
        run('--no-images')
        self.assertFalse(
            Quiz.objects.filter(lesson__module__category__slug='ai', is_generated=True).exists()
        )

    def test_bazada_ham_bitta_togri_javob(self):
        run('--no-images')
        for question in Question.objects.filter(quiz__lesson__module__category__slug='ai'):
            with self.subTest(savol=question.text[:50]):
                self.assertEqual(question.choices.filter(is_correct=True).count(), 1)

    # ────────────────── Qayta ishga tushirish ──────────────────

    def test_ikkinchi_yurish_nusxa_yaratmaydi(self):
        run('--no-images')
        before = {
            'lessons': Lesson.objects.count(),
            'modules': Module.objects.count(),
            'quizzes': Quiz.objects.count(),
            'questions': Question.objects.count(),
            'choices': Choice.objects.count(),
        }

        run('--no-images')

        self.assertEqual(before['lessons'], Lesson.objects.count())
        self.assertEqual(before['modules'], Module.objects.count())
        self.assertEqual(before['quizzes'], Quiz.objects.count())
        self.assertEqual(before['questions'], Question.objects.count())
        self.assertEqual(before['choices'], Choice.objects.count())

    def test_ikkinchi_yurish_dars_id_sini_saqlaydi(self):
        """
        ID o'zgarsa o'quvchilarning o'zlashtirishi (`UserProgress`) va
        test natijalari boshqa darsga bog'lanib qolardi.
        """
        run('--no-images')
        before = dict(
            Lesson.objects.filter(module__category__slug='ai').values_list('title', 'id')
        )

        run('--no-images')
        after = dict(
            Lesson.objects.filter(module__category__slug='ai').values_list('title', 'id')
        )

        self.assertEqual(before, after)

    def test_matn_yangilanadi(self):
        run('--no-images')
        lesson = Lesson.objects.filter(module__category__slug='ai').first()
        lesson.theory = 'eskirgan matn'
        lesson.save(update_fields=['theory'])

        run('--no-images')

        lesson.refresh_from_db()
        self.assertNotEqual(lesson.theory, 'eskirgan matn')

    # ────────────────── Rasmlar ──────────────────

    def test_sxemalar_chiziladi(self):
        run()
        expected = sum(
            1 for m in MODULES for l in m['lessons'] if l.get('image')
        )
        self.assertEqual(
            LessonImage.objects.filter(lesson__module__category__slug='ai').count(), expected
        )

    def test_qayta_yurishda_rasm_ikkilanmaydi(self):
        """Eski rasm o'chirilmasa dars oxirida bir nechta nusxa turib qolardi."""
        run()
        before = LessonImage.objects.filter(lesson__module__category__slug='ai').count()
        run()
        self.assertEqual(
            LessonImage.objects.filter(lesson__module__category__slug='ai').count(), before
        )

    def test_no_images_bayrogi_rasm_yaratmaydi(self):
        run('--no-images')
        self.assertEqual(
            LessonImage.objects.filter(lesson__module__category__slug='ai').count(), 0
        )

    # ────────────────── dry-run ──────────────────

    def test_dry_run_bazaga_tegmaydi(self):
        output = run('--dry-run')
        self.assertFalse(Category.objects.filter(slug='ai').exists())
        self.assertIn('dry-run', output)
