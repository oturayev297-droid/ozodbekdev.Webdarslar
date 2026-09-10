"""
Test mazmuni to'g'riligi.

Ilgari yettita testda har savol ikki marta turardi, ikkitasida esa
boshqa kursning savollari bor edi ("Ro'yhat va uning metodlari" da
JavaScript). Buni hech bir test sezmasdi — sahifa ishlab turardi.

Bu yerda ikki narsa sinaladi:
  * fixture (`content.json`) — yangi bazaga xato qayta yuklanmasin;
  * 0026 migratsiyasining qoidalari — production'dagi eski holat
    tuzatiladi, admin qo'lda o'zgartirgan testga esa tegilmaydi.

Ishga tushirish:  python manage.py test core.tests_quiz_content
"""

import importlib
import json
from pathlib import Path

from django.apps import apps
from django.test import SimpleTestCase, TestCase

from .models import Category, Choice, Lesson, Module, Question, Quiz

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'content.json'

m0026 = importlib.import_module('core.migrations.0026_fix_quiz_questions')


class FixtureQuizTests(SimpleTestCase):
    """Bazasiz — faqat fixture faylini o'qiydi."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        data = json.loads(FIXTURE.read_text(encoding='utf-8'))
        cls.questions = [o for o in data if o['model'] == 'core.question']
        cls.choices = [o for o in data if o['model'] == 'core.choice']
        cls.lessons = [o for o in data if o['model'] == 'core.lesson']

    def test_testda_takror_savol_yoq(self):
        seen = set()
        for q in self.questions:
            key = (q['fields']['quiz'], m0026.normalize(q['fields']['text']))
            with self.subTest(savol=q['fields']['text']):
                self.assertNotIn(key, seen)
            seen.add(key)

    def test_har_savolda_bitta_togri_javob(self):
        correct = {}
        for c in self.choices:
            if c['fields']['is_correct']:
                qpk = c['fields']['question']
                correct[qpk] = correct.get(qpk, 0) + 1
        for q in self.questions:
            with self.subTest(savol=q['fields']['text']):
                self.assertEqual(correct.get(q['pk']), 1)

    def test_python_royxat_testida_javascript_yoq(self):
        texts = [q['fields']['text'] for q in self.questions if q['fields']['quiz'] == 11]
        self.assertTrue(texts)
        self.assertFalse([t for t in texts if 'JavaScript' in t or 'DOM' in t])

    def test_react_testi_reactga_oid(self):
        texts = " ".join(q['fields']['text'] for q in self.questions if q['fields']['quiz'] == 6)
        self.assertIn("React", texts)
        self.assertNotIn("DOM nima", texts)

    def test_python_testlari_bir_biridan_farq_qiladi(self):
        """Kirish, Lesson 1 va Lesson 2 testlari aynan bir xil edi."""
        def texts(quiz_id):
            return {m0026.normalize(q['fields']['text'])
                    for q in self.questions if q['fields']['quiz'] == quiz_id}

        self.assertNotEqual(texts(8), texts(9))
        self.assertNotEqual(texts(10), texts(9))

    def test_fixture_darslari_bepul(self):
        """
        Yangi bo'sh bazada 0025 hech narsa topmaydi (darslar keyin,
        `seed_content` bilan yuklanadi) — shuning uchun fixture'ning
        o'zi ham bepul bo'lishi kerak.
        """
        paid = [l['pk'] for l in self.lessons if not l['fields']['is_free']]
        self.assertEqual(paid, [])

    def test_yangi_savollarda_bitta_togri_javob_va_orni_aylanadi(self):
        for quiz_id, (_, _, questions) in m0026.REPLACEMENTS.items():
            positions = set()
            for i, (_, correct, wrong) in enumerate(questions):
                items = m0026.choices(i, correct, wrong)
                self.assertEqual(sum(ok for _, ok in items), 1)
                self.assertEqual(len({text for text, _ in items}), 4, "variantlar takrorlanmasin")
                positions.add(next(n for n, (_, ok) in enumerate(items) if ok))
            with self.subTest(test=quiz_id):
                self.assertEqual(positions, {0, 1, 2, 3})


class MigrationRuleTests(TestCase):
    """0026 qoidalari — production'dagi eski holatga o'xshash bazada."""

    def setUp(self):
        category = Category.objects.create(name="Python", slug="python")
        module = Module.objects.create(category=category, title="M", order=1)
        self.lesson = Lesson.objects.create(module=module, title="Dars", order=1)
        self.quiz = Quiz.objects.create(lesson=self.lesson, title="Test")

    def _question(self, text, correct='A', quiz=None):
        question = Question.objects.create(quiz=quiz or self.quiz, text=text)
        for option in 'ABCD':
            Choice.objects.create(question=question, text=option, is_correct=option == correct)
        return question

    def test_aynan_takror_ochiriladi(self):
        first = self._question("1. Python qanday til?")
        self._question("16. Python qanday til?")

        m0026.remove_duplicates(apps, None)

        self.assertEqual(list(self.quiz.questions.all()), [first])

    def test_variantlari_boshqa_takrorga_tegilmaydi(self):
        self._question("1. Python qanday til?", correct='A')
        self._question("16. Python qanday til?", correct='B')

        m0026.remove_duplicates(apps, None)

        self.assertEqual(self.quiz.questions.count(), 2)

    def _broken_quiz(self, quiz_id, lesson, first_text):
        quiz = Quiz.objects.create(pk=quiz_id, lesson=lesson, title="Eski")
        self._question(f"1. {first_text}", quiz=quiz)
        for n in range(2, m0026.OLD_UNIQUE_COUNT + 1):
            self._question(f"{n}. Savol {n}", quiz=quiz)
        return quiz

    def _lesson(self, pk):
        return Lesson.objects.create(pk=pk, module=self.lesson.module, title=f"D{pk}", order=pk)

    def test_eski_holatdagi_test_almashtiriladi(self):
        quiz = self._broken_quiz(11, self._lesson(33), "JavaScript qanday til?")

        m0026.replace_off_topic(apps, None)

        texts = list(quiz.questions.order_by('id').values_list('text', flat=True))
        self.assertEqual(len(texts), len(m0026.ROYXAT_METODLARI))
        self.assertTrue(texts[0].startswith("1. Ro'yxat oxiriga"))
        for question in quiz.questions.all():
            self.assertEqual(question.choices.filter(is_correct=True).count(), 1)

    def test_admin_ozgartirgan_testga_tegilmaydi(self):
        quiz = self._broken_quiz(11, self._lesson(33), "Admin yozgan savol")

        m0026.replace_off_topic(apps, None)

        self.assertTrue(quiz.questions.filter(text="1. Admin yozgan savol").exists())
