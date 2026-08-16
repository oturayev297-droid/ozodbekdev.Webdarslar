"""
Ota-onaga haftalik Telegram hisoboti.

E'TIBOR QARATILGAN JOYLAR:

  * FAQAT BOG'LANGAN ota-onaga borishi — begona odam bolaning
    natijalarini olmasligi
  * Telegram ulanmagan ota-ona buyruqni yiqitmasligi
  * Bo'sh hafta ochiq aytilishi — aynan shu holat uchun xabar kerak
"""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core import study_time
from core.management.commands.parent_weekly_report import build_message
from core.models import (
    Category,
    Lesson,
    Module,
    ParentLink,
    Quiz,
    QuizResult,
    StudySession,
    UserProgress,
)


def make_user(username, chat_id=''):
    user = User.objects.create_user(username, password='juda-maxfiy-parol-7')
    profile = user.profile
    profile.telegram_chat_id = chat_id
    profile.save(update_fields=['telegram_chat_id'])
    return user


@override_settings(TELEGRAM_BOT_TOKEN='test-token', TELEGRAM_ADMIN_CHAT_IDS=[])
class ParentWeeklyReportTests(TestCase):
    def setUp(self):
        self.parent = make_user('otasi', chat_id='555')
        self.child = make_user('farzand')
        ParentLink.objects.create(
            parent=self.parent, student=self.child, relation='Otasi'
        )

        category = Category.objects.create(name='B', slug='b')
        module = Module.objects.create(category=category, title='M', order=1)
        self.lesson = Lesson.objects.create(module=module, title='D', order=1)

    def _run(self, **kwargs):
        with patch('billing.telegram.send', return_value=True) as sent:
            call_command('parent_weekly_report', **kwargs)
        return sent

    def test_boglangan_ota_onaga_yuboriladi(self):
        sent = self._run()

        sent.assert_called_once()
        chat_id, text = sent.call_args[0]
        self.assertEqual(chat_id, '555')
        self.assertIn('farzand', text)

    def test_BOGLANMAGAN_odamga_YUBORILMAYDI(self):
        """
        Eng muhim tekshiruv: hisobot shaxsiy ma'lumot. Bog'lanishsiz
        odam ro'yxatga tushib qolsa, begona bolaning natijalari
        uning Telegramiga borardi.
        """
        make_user('begona', chat_id='999')

        sent = self._run()

        self.assertEqual(sent.call_count, 1)
        self.assertEqual(sent.call_args[0][0], '555')

    def test_telegram_ulanmagan_ota_ona_otkazib_yuboriladi(self):
        ParentLink.objects.create(
            parent=make_user('onasi'), student=self.child, relation='Onasi'
        )

        sent = self._run()

        # Ulanmagani xato emas — u hisobotni sahifadan ko'raveradi
        self.assertEqual(sent.call_count, 1)

    def test_token_yoq_bolsa_hech_narsa_yuborilmaydi(self):
        with override_settings(TELEGRAM_BOT_TOKEN=''):
            sent = self._run()

        self.assertEqual(sent.call_count, 0)

    def test_dry_run_yubormaydi(self):
        sent = self._run(dry_run=True)

        self.assertEqual(sent.call_count, 0)


class MessageTextTests(TestCase):
    """Xabar matni."""

    def setUp(self):
        self.parent = make_user('ota2', chat_id='1')
        self.child = make_user('bola2')
        self.link = ParentLink.objects.create(parent=self.parent, student=self.child)

        category = Category.objects.create(name='B', slug='b')
        module = Module.objects.create(category=category, title='M', order=1)
        self.lesson = Lesson.objects.create(module=module, title='D', order=1)

    def test_bosh_hafta_ochiq_aytiladi(self):
        text = build_message(self.link)

        self.assertIn('Bu hafta darsga kirmadi', text)

    def test_vaqt_va_natijalar_korinadi(self):
        StudySession.objects.create(user=self.child, date=study_time.today(), seconds=7200)
        quiz = Quiz.objects.create(lesson=self.lesson, title='T', is_published=True)
        QuizResult.objects.create(
            user=self.child, quiz=quiz, score_percentage=80,
            correct_count=4, total_questions=5,
        )
        UserProgress.objects.create(user=self.child, lesson=self.lesson, is_completed=True)

        text = build_message(self.link)

        self.assertIn('2.0 soat', text)
        self.assertIn('80%', text)
        self.assertIn('100%', text)          # 1/1 dars
        self.assertNotIn('darsga kirmadi', text)

    def test_eski_test_hisobga_olinmaydi(self):
        """
        Hisobot HAFTALIK. Bir oy oldingi natija ham qo'shilsa, ota-ona
        bola bu hafta ishlagan deb o'ylardi.
        """
        quiz = Quiz.objects.create(lesson=self.lesson, title='T', is_published=True)
        old = QuizResult.objects.create(
            user=self.child, quiz=quiz, score_percentage=90,
            correct_count=9, total_questions=10,
        )
        QuizResult.objects.filter(pk=old.pk).update(
            completed_at=timezone.now() - timedelta(days=30)
        )

        text = build_message(self.link)

        self.assertIn('Test topshirmagan', text)

    def test_ismdagi_teg_belgilari_olib_tashlanadi(self):
        """
        Xabar HTML `parse_mode` bilan ketadi. Ismga `<b>` yozib
        qo'yilsa, Telegram uni teg deb o'qib xabarni buzardi.
        """
        profile = self.child.profile
        profile.full_name = "<b>Ali</b>"
        profile.save(update_fields=['full_name'])

        text = build_message(self.link)

        self.assertIn('bAli/b', text)
        self.assertNotIn('<b>Ali', text)
