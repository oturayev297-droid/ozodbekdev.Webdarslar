"""
So'rovlar soni (N+1 qo'riqchisi).

NEGA KERAK: N+1 nuqsoni testlarda ko'rinmaydi — javob to'g'ri
qaytadi, faqat sekin. Kichik bazada bu sezilmaydi va faqat
o'quvchilar ko'paygach, ya'ni eng yomon paytda bilinadi.

Aynan shunday nuqson bor edi: testlar ro'yxati har bir test uchun
obuna holatini bazadan qayta o'qirdi — 45 ta testli sahifada 95 ta
so'rov. Darvoza bir marta ochiladigan bo'lgach 7 ta qoldi.

BUDJET DARSLAR SONIGA BOG'LIQ EMAS. Quyidagi chegaralar aynan shuni
tekshiradi: ma'lumot ko'paysa ham so'rov soni o'zgarmasligi kerak.
"""

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from billing.models import PaymentMethod, PeriodSource
from billing.services import extend_subscription
from core.models import (
    Category,
    Choice,
    Lesson,
    Module,
    Project,
    Question,
    Quiz,
)

#: Har bir manzil uchun eng ko'p so'rov. Sahifadagi ma'lumot
#: hajmidan QAT'I NAZAR shu chegarada qolishi kerak.
BUDGETS = {
    '/api/v1/courses/': 10,
    '/api/v1/quizzes/': 10,
    '/api/v1/projects/': 6,
    '/api/v1/dashboard/': 12,
    '/api/v1/certificates/': 6,
    '/api/v1/subscription/': 8,
}


def build_content(categories=3, modules=3, lessons=5):
    for c in range(categories):
        category = Category.objects.create(name=f'B{c}', slug=f'b{c}')
        for m in range(modules):
            module = Module.objects.create(category=category, title=f'M{m}', order=m)
            for order in range(lessons):
                lesson = Lesson.objects.create(module=module, title=f'D{order}', order=order)
                quiz = Quiz.objects.create(lesson=lesson, title=f'T{order}', is_published=True)
                for q in range(5):
                    question = Question.objects.create(quiz=quiz, text=f'S{q}')
                    for ch in range(4):
                        Choice.objects.create(
                            question=question, text=f'V{ch}', is_correct=(ch == 0)
                        )


def make_subscriber(username):
    user = User.objects.create_user(username, password='juda-maxfiy-parol-9')
    profile = user.profile
    profile.is_approved = True
    profile.save(update_fields=['is_approved'])
    extend_subscription(
        user, months=1, source=PeriodSource.PAYMENT,
        payment_method=PaymentMethod.CASH, amount_tiyin=10_000_000,
    )
    return user


class QueryBudgetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_content()
        for i in range(20):
            Project.objects.create(title=f'L{i}', description='x', tech_stack='y', order=i)
        cls.user = make_subscriber('olchov')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def _count(self, url) -> int:
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(ctx)

    def test_budjetdan_oshmaydi(self):
        for url, budget in BUDGETS.items():
            with self.subTest(url=url):
                count = self._count(url)
                self.assertLessEqual(
                    count, budget,
                    f"{url}: {count} ta so'rov, chegara {budget}. "
                    f"Sikl ichida bazaga murojaat qilinmayotganini tekshiring."
                )

    def test_kurs_ichi_budjetdan_oshmaydi(self):
        count = self._count('/api/v1/courses/b0/')
        self.assertLessEqual(count, 16, f"Kurs ichi: {count} ta so'rov")


class ScalingTests(TestCase):
    """
    ENG MUHIM TEKSHIRUV: ma'lumot ikki barobar ko'paysa, so'rov soni
    O'ZGARMASLIGI kerak. Oshsa — sikl ichida bazaga murojaat bor.
    """

    def _measure(self, url, lessons):
        Quiz.objects.all().delete()
        Lesson.objects.all().delete()
        Module.objects.all().delete()
        Category.objects.all().delete()
        build_content(categories=2, modules=2, lessons=lessons)

        client = Client()
        client.force_login(self.user)
        with CaptureQueriesContext(connection) as ctx:
            client.get(url)
        return len(ctx)

    def setUp(self):
        self.user = make_subscriber('olchov2')

    def test_testlar_royxati_ozgarmaydi(self):
        kam = self._measure('/api/v1/quizzes/', lessons=2)
        kop = self._measure('/api/v1/quizzes/', lessons=8)

        self.assertEqual(
            kam, kop,
            f"Dars soni 4 barobar oshganda so'rov {kam} -> {kop} bo'ldi. "
            f"Bu N+1 nuqsoni."
        )

    def test_kurslar_royxati_ozgarmaydi(self):
        kam = self._measure('/api/v1/courses/', lessons=2)
        kop = self._measure('/api/v1/courses/', lessons=8)

        self.assertEqual(kam, kop, f"Kurslar ro'yxati: {kam} -> {kop}")

    def test_kurs_ichi_ozgarmaydi(self):
        kam = self._measure('/api/v1/courses/b0/', lessons=2)
        kop = self._measure('/api/v1/courses/b0/', lessons=8)

        self.assertEqual(kam, kop, f"Kurs ichi: {kam} -> {kop}")
