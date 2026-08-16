"""
Panelning yangi bo'limlari
==========================

Bu bo'limlar Django admini o'chirilgach yozildi. Ilgari kartalar,
narx, bo'limlar va test savollari FAQAT admin orqali boshqarilardi —
ya'ni bu testlar tekshirayotgan yo'llar tizimning yagona yo'li.

E'TIBOR QARATILGAN JOYLAR:

  * KARTA — ularsiz hech kim to'lay olmaydi
  * NARX — so'm/tiyin aylanishi va o'tgan tushumga tegmasligi
  * OTA-ONA — bog'lanishni faqat admin yaratishi
  * SAVOL — to'g'ri javobsiz savol saqlanmasligi
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from billing import services
from billing.models import (
    AdminSetting,
    PaymentMethod,
    PeriodSource,
    SubscriptionPeriod,
)
from billing.services import extend_subscription
from core.models import (
    Category, Choice, Lesson, Module, ParentLink, Project, Question, Quiz,
)

from .tests import make_plan, make_user


class SettingsCardTests(TestCase):
    """
    Karta rekvizitlari.

    ENG MUHIM BO'LIM: karta ro'yxati bo'sh bo'lsa o'quvchi pul o'tkaza
    olmaydi va tizim daromad keltirmaydi. Ilgari bu ma'lumot Django
    admini orqali kiritilardi.
    """

    def setUp(self):
        make_plan()
        self.staff = make_user('kartachi', staff=True)
        self.client.force_login(self.staff)
        self.url = reverse('panel:settings_cards')

    def test_karta_saqlanadi(self):
        response = self.client.post(self.url, {
            'number': ['8600 1234 5678 9012'],
            'holder': ['OZODBEK O'],
            'bank': ['Kapitalbank'],
            'note': [''],
        })

        self.assertRedirects(response, reverse('panel:settings'))

        cards = services.get_cards()
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['holder'], 'OZODBEK O')

    def test_bir_nechta_karta_saqlanadi(self):
        self.client.post(self.url, {
            'number': ['8600 1111 1111 1111', '9860 2222 2222 2222'],
            'holder': ['Birinchi', 'Ikkinchi'],
            'bank': ['Kapital', 'Humo'],
            'note': ['', 'zaxira'],
        })

        self.assertEqual(len(services.get_cards()), 2)

    def test_bosh_qator_saqlanmaydi(self):
        """
        Formada har doim bitta bo'sh qator turadi — u karta emas.
        """
        self.client.post(self.url, {
            'number': ['8600 1111 1111 1111', '', '   '],
            'holder': ['Birinchi', '', ''],
            'bank': ['Kapital', '', ''],
            'note': ['', '', ''],
        })

        self.assertEqual(len(services.get_cards()), 1)

    def test_kartalar_butunlay_almashtiriladi(self):
        """
        Saqlash — QO'SHISH emas, ALMASHTIRISH.

        Admin qatorni o'chirib saqlasa, o'sha karta yo'qolishi kerak.
        Aks holda eski, yopilgan kartaga pul yuborilaverardi.
        """
        self.client.post(self.url, {
            'number': ['8600 1111 1111 1111', '9860 2222 2222 2222'],
            'holder': ['Birinchi', 'Ikkinchi'], 'bank': ['A', 'B'], 'note': ['', ''],
        })
        self.client.post(self.url, {
            'number': ['9860 2222 2222 2222'],
            'holder': ['Ikkinchi'], 'bank': ['B'], 'note': [''],
        })

        cards = services.get_cards()
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]['holder'], 'Ikkinchi')

    def test_notogri_karta_qabul_qilinmaydi(self):
        response = self.client.post(self.url, {
            'number': ['123'], 'holder': ['X'], 'bank': ['Y'], 'note': [''],
        })

        self.assertRedirects(response, reverse('panel:settings'))
        self.assertEqual(services.get_cards(), [])

    def test_oquvchi_kartani_ozgartira_olmaydi(self):
        self.client.force_login(make_user('oddiy1'))

        response = self.client.post(self.url, {
            'number': ['8600 1111 1111 1111'], 'holder': ['Yomon'],
            'bank': ['X'], 'note': [''],
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(services.get_cards(), [])


class SettingsPriceTests(TestCase):
    """Tarif narxi."""

    def setUp(self):
        # AYNAN `services.get_plan()` qaytaradigan tarif. `make_plan()`
        # test uchun boshqa kodli tarif yaratadi — kod uni o'qimaydi.
        self.plan = services.get_plan()
        self.staff = make_user('narxchi', staff=True)
        self.client.force_login(self.staff)
        self.url = reverse('panel:settings_price')

    def test_narx_somdan_tiyinga_aylanadi(self):
        self.client.post(self.url, {'price': '150000'})

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.price_per_month_tiyin, 15_000_000)

    def test_juda_kichik_narx_rad_etiladi(self):
        self.client.post(self.url, {'price': '10'})

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.price_per_month_tiyin, services.DEFAULT_PRICE_TIYIN)

    def test_juda_katta_narx_rad_etiladi(self):
        self.client.post(self.url, {'price': '99000000'})

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.price_per_month_tiyin, services.DEFAULT_PRICE_TIYIN)

    def test_harf_yiqitmaydi(self):
        response = self.client.post(self.url, {'price': 'juda arzon'})

        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.price_per_month_tiyin, services.DEFAULT_PRICE_TIYIN)

    def test_otgan_tushum_ozgarmaydi(self):
        """
        NARX O'ZGARSA O'TGAN HISOBOT O'ZGARMAYDI.

        Har davrga summa muzlatib yozilgan. Agar hisobot joriy narxdan
        hisoblanganida, narx ko'tarilishi bilan o'tgan oylarning
        daromadi ham "o'sib" ketardi — bu soxta hisobot.
        """
        student = make_user('tolovchi')
        paid = services.DEFAULT_PRICE_TIYIN
        extend_subscription(
            student, months=1, source=PeriodSource.PAYMENT,
            payment_method=PaymentMethod.CASH, amount_tiyin=paid,
        )

        self.client.post(self.url, {'price': '200000'})

        period = SubscriptionPeriod.objects.get(subscription__user=student)
        self.assertEqual(period.amount_tiyin, paid)


class CategoryTests(TestCase):
    """Bo'limlar — ilgari faqat Django admini orqali qo'shilardi."""

    def setUp(self):
        make_plan()
        self.staff = make_user('bolimchi', staff=True)
        self.client.force_login(self.staff)

    def test_bolim_yaratiladi(self):
        response = self.client.post(reverse('panel:category_new'), {
            'name': 'Sun\'iy intellekt',
            'slug': 'ai',
            'description': 'AI asoslari',
            'icon': 'cpu',
            'order': '1',
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Category.objects.filter(slug='ai').exists())

    def test_bolim_tahrirlanadi(self):
        category = Category.objects.create(name='Eski', slug='eski')

        self.client.post(reverse('panel:category_edit', args=[category.id]), {
            'name': 'Yangi nom', 'slug': 'eski', 'description': '',
            'icon': '', 'order': '0',
        })

        category.refresh_from_db()
        self.assertEqual(category.name, 'Yangi nom')

    def test_darsli_bolim_ochirilmaydi(self):
        """
        Ichida dars bo'lgan bo'lim o'chirilsa, darslar ham ketardi
        (`on_delete=CASCADE`). Tasodifiy bosishdan himoya.
        """
        category = Category.objects.create(name='To\'la', slug='tola')
        module = Module.objects.create(category=category, title='M1', order=1)
        Lesson.objects.create(module=module, title='D1', order=1)

        self.client.post(reverse('panel:category_delete', args=[category.id]))

        self.assertTrue(Category.objects.filter(pk=category.pk).exists())

    def test_bosh_bolim_ochiriladi(self):
        category = Category.objects.create(name='Bo\'sh', slug='bosh')

        self.client.post(reverse('panel:category_delete', args=[category.id]))

        self.assertFalse(Category.objects.filter(pk=category.pk).exists())


class QuestionTests(TestCase):
    """
    Test savollari.

    Ilgari savol va javob variantlari Django admini orqali
    kiritilardi — bu bo'limsiz yangi test yozib bo'lmasdi.
    """

    def setUp(self):
        make_plan()
        self.staff = make_user('savolchi', staff=True)
        self.client.force_login(self.staff)

        category = Category.objects.create(name='B', slug='b')
        module = Module.objects.create(category=category, title='M', order=1)
        lesson = Lesson.objects.create(module=module, title='D', order=1)
        self.quiz = Quiz.objects.create(lesson=lesson, title='Test', is_published=False)

    def _post(self, **overrides):
        data = {
            'text': '2 + 2 nechchi?',
            'order': '1',
            'choice_text': ['3', '4', '5'],
            'correct': '1',
        }
        data.update(overrides)
        return self.client.post(reverse('panel:question_save', args=[self.quiz.id]), data)

    def test_savol_va_variantlar_saqlanadi(self):
        self._post()

        question = Question.objects.get(quiz=self.quiz)
        self.assertEqual(question.choices.count(), 3)
        self.assertEqual(question.choices.get(is_correct=True).text, '4')

    def test_togri_javobsiz_savol_saqlanmaydi(self):
        """
        To'g'ri javobi yo'q savol testni buzardi: uni yechgan har bir
        o'quvchi xato qilgan hisoblanardi va hech kim o'ta olmasdi.
        """
        self._post(correct='')

        self.assertEqual(Question.objects.filter(quiz=self.quiz).count(), 0)

    def test_bitta_variantli_savol_saqlanmaydi(self):
        self._post(choice_text=['4'], correct='0')

        self.assertEqual(Question.objects.filter(quiz=self.quiz).count(), 0)

    def test_bosh_variant_hisobga_olinmaydi(self):
        self._post(choice_text=['3', '4', '', '   '], correct='1')

        question = Question.objects.get(quiz=self.quiz)
        self.assertEqual(question.choices.count(), 2)

    def test_savol_ochiriladi(self):
        self._post()
        question = Question.objects.get(quiz=self.quiz)

        self.client.post(reverse('panel:question_delete', args=[question.id]))

        self.assertFalse(Question.objects.filter(pk=question.pk).exists())
        # Variantlar ham ketishi kerak — yetim qator qolmasin
        self.assertEqual(Choice.objects.filter(question_id=question.pk).count(), 0)

    def test_savollar_sahifasi_ochiladi(self):
        response = self.client.get(reverse('panel:quiz_questions', args=[self.quiz.id]))
        self.assertEqual(response.status_code, 200)

    def test_oquvchi_savol_qosha_olmaydi(self):
        self.client.force_login(make_user('oddiy2'))

        self._post()

        self.assertEqual(Question.objects.filter(quiz=self.quiz).count(), 0)


class ParentLinkFormTests(TestCase):
    """
    Bog'lash formasining chetki holatlari.

    Asosiy qoidalar (kim bog'lay oladi, takror, uzish)
    `core.tests_study_time.ParentPanelTests` da sinaladi. Bu yerda
    faqat forma noto'g'ri to'ldirilgan holatlar.
    """

    def setUp(self):
        make_plan()
        self.staff = make_user('adminp', staff=True)
        self.parent = make_user('ota')
        self.student = make_user('farzand')
        self.client.force_login(self.staff)

    def test_yoq_foydalanuvchi_yiqitmaydi(self):
        response = self.client.post(reverse('panel:parent_link_create'), {
            'parent': 999999, 'student': self.student.id, 'relation': '',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ParentLink.objects.count(), 0)

    def test_bosh_maydon_yiqitmaydi(self):
        response = self.client.post(reverse('panel:parent_link_create'), {})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ParentLink.objects.count(), 0)

    def test_sahifa_ochiladi(self):
        ParentLink.objects.create(
            parent=self.parent, student=self.student, created_by=self.staff,
        )

        response = self.client.get(reverse('panel:parents'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'farzand')


class ProjectTests(TestCase):
    """
    Amaliy loyihalar.

    Ilgari loyiha qo'shish uchun `manage.py shell` ochish kerak edi —
    model bor edi, lekin uni faqat Django admini ko'rsatardi.
    """

    def setUp(self):
        make_plan()
        self.staff = make_user('loyihachi', staff=True)
        self.client.force_login(self.staff)

    def _data(self, **overrides):
        data = {
            'title': "To'lov boti",
            'description': "Telegram bot yozing",
            'difficulty': 'Entry',
            'tech_stack': 'Python, Django',
            'image_url': '', 'demo_url': '', 'repo_url': '',
            'order': '1',
        }
        data.update(overrides)
        return data

    def test_loyiha_yaratiladi(self):
        response = self.client.post(reverse('panel:project_new'), self._data())

        self.assertRedirects(response, reverse('panel:projects'))
        project = Project.objects.get(title="To'lov boti")
        self.assertEqual(project.tech_stack, 'Python, Django')

    def test_nomsiz_loyiha_saqlanmaydi(self):
        self.client.post(reverse('panel:project_new'), self._data(title=''))

        self.assertEqual(Project.objects.count(), 0)

    def test_notogri_havola_qabul_qilinmaydi(self):
        self.client.post(reverse('panel:project_new'), self._data(demo_url='shunchaki matn'))

        self.assertEqual(Project.objects.count(), 0)

    def test_loyiha_tahrirlanadi(self):
        project = Project.objects.create(
            title='Eski', description='x', tech_stack='Python',
        )

        self.client.post(
            reverse('panel:project_edit', args=[project.id]),
            self._data(title='Yangi nom'),
        )

        project.refresh_from_db()
        self.assertEqual(project.title, 'Yangi nom')

    def test_loyiha_ochiriladi(self):
        project = Project.objects.create(
            title="O'chadi", description='x', tech_stack='Python',
        )

        self.client.post(reverse('panel:project_delete', args=[project.id]))

        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_royxat_tartib_boyicha(self):
        Project.objects.create(title='Ikkinchi', description='x', tech_stack='y', order=2)
        Project.objects.create(title='Birinchi', description='x', tech_stack='y', order=1)

        response = self.client.get(reverse('panel:projects'))

        titles = [p.title for p in response.context['page_obj']]
        self.assertEqual(titles, ['Birinchi', 'Ikkinchi'])

    def test_oquvchi_loyiha_qosha_olmaydi(self):
        self.client.force_login(make_user('oddiy3'))

        response = self.client.post(reverse('panel:project_new'), self._data())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Project.objects.count(), 0)


class NewPageRenderTests(TestCase):
    """Yangi sahifalar bo'sh bazada ham ochilishi."""

    def setUp(self):
        make_plan()
        self.client.force_login(make_user('admin7', staff=True))

    def test_bosh_bazada_ochiladi(self):
        for name in ('settings', 'parents', 'projects'):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(f'panel:{name}')).status_code, 200)

    def test_yangi_bolim_formasi_ochiladi(self):
        self.assertEqual(self.client.get(reverse('panel:category_new')).status_code, 200)
        self.assertEqual(self.client.get(reverse('panel:project_new')).status_code, 200)

    def test_sozlamalarda_karta_va_narx_korinadi(self):
        AdminSetting.objects.update_or_create(
            key='payment_cards',
            defaults={'value': [{
                'number': '8600 1111 1111 1111', 'holder': 'Test',
                'bank': 'Kapital', 'note': '',
            }]},
        )

        response = self.client.get(reverse('panel:settings'))

        self.assertContains(response, '8600')
        # Narx SO'MDA ko'rsatiladi — formaga ham so'mda kiritiladi
        self.assertContains(response, str(services.get_plan().price_per_month_tiyin // 100))
