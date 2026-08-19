"""
`seed_content` buyrug'i testlari.

Buyruq PRODUCTION DEPLOYIDA, har safar ishga tushadi. Shuning uchun
eng muhim tekshiruv "yukladimi" emas — IKKINCHI MARTA ishlaganda
adminning o'zgarishlarini bosib ketmasligi.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.models import Category, Challenge, Lesson, Project


class SeedContentTests(TestCase):
    def _seed(self, *args):
        out = StringIO()
        call_command('seed_content', *args, stdout=out, stderr=out, verbosity=0)
        return out.getvalue()

    def test_bosh_bazaga_mazmun_yuklanadi(self):
        self._seed()

        # Har bo'lim uchun alohida: bittasi yuklanib, qolgani
        # tushib qolsa ham test o'tib ketmasin.
        self.assertTrue(Category.objects.exists())
        self.assertTrue(Lesson.objects.exists())
        self.assertTrue(Project.objects.exists())
        self.assertTrue(Challenge.objects.exists())

    def test_ikkinchi_marta_ustiga_yozmaydi(self):
        self._seed()

        lesson = Lesson.objects.first()
        lesson.title = "Admin panelda o'zgartirgan sarlavha"
        lesson.save()

        self._seed()

        lesson.refresh_from_db()
        self.assertEqual(lesson.title, "Admin panelda o'zgartirgan sarlavha")

    def test_force_bilan_ustiga_yoziladi(self):
        self._seed()

        lesson = Lesson.objects.first()
        original = lesson.title
        lesson.title = "Vaqtinchalik"
        lesson.save()

        self._seed('--force')

        lesson.refresh_from_db()
        self.assertEqual(lesson.title, original)

    def test_dry_run_hech_narsa_yozmaydi(self):
        self._seed('--dry-run')
        self.assertFalse(Category.objects.exists())

    def test_yuklash_xatosi_deployni_toxtatmaydi(self):
        """
        Buyruq `startCommand` zanjirida gunicorn'dan oldin turadi.
        Xato yuqoriga chiqsa, server umuman ko'tarilmasdi.
        """
        from unittest.mock import patch

        with patch('core.management.commands.seed_content.call_command',
                   side_effect=RuntimeError('fixture buzilgan')):
            output = self._seed()

        self.assertIn('buzilgan', output)
        self.assertFalse(Category.objects.exists())
