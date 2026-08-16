"""
Production sozlamalari.

NEGA ALOHIDA FAYL VA NEGA SUBPROTSESS: sozlamalar modul sifatida bir
marta yuklanadi va lokalda u DOIM `DEBUG=True` bilan yuklanadi. Ya'ni
`if not DEBUG` ichidagi kod na ishlab chiqishda, na oddiy testlarda
bajariladi — u faqat serverda, birinchi deployda ishga tushadi.

Aynan shu sabab jiddiy nuqson yashirinib qolgan edi:
`CSRF_TRUSTED_ORIGINS` ro'yxat yaratilishidan 117 qator OLDIN
to'ldirilardi va `DJANGO_DEBUG=False` bilan sozlamalar `NameError`
bilan yiqilardi. Server umuman ko'tarilmasdi.

Shuning uchun bu yerdagi testlar sozlamalarni ALOHIDA JARAYONDA,
production muhit o'zgaruvchilari bilan yuklaydi.
"""

import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parent.parent

#: Productionga o'xshash muhit. `.env` dagi qiymatlar ustidan yoziladi.
PROD_ENV = {
    'DJANGO_DEBUG': 'False',
    # Django 50 belgidan qisqa kalitga ogohlantirish beradi —
    # shuning uchun bu yerda ham to'laqonli uzunlik.
    'DJANGO_SECRET_KEY': 'x7Kq2mZ9pL4vR8tN3wS6yB1dF5gH0jC-uA_eQiOoPzXcVbNmMkLjHgFdSaRtYuIo',
    'DJANGO_ALLOWED_HOSTS': 'oson.uz,www.oson.uz',
    'FRONTEND_ORIGINS': 'https://oson.vercel.app',
    'FRONTEND_URL': 'https://oson.vercel.app',
    'DATABASE_URL': '',
}


def run_in_prod(code: str) -> subprocess.CompletedProcess:
    """Berilgan kodni production sozlamalari bilan alohida ishga tushiradi."""
    env = {**os.environ, **PROD_ENV, 'DJANGO_SETTINGS_MODULE': 'stitch_backend.settings'}
    return subprocess.run(
        [sys.executable, '-c', f"import django; django.setup()\n{code}"],
        cwd=BASE_DIR, env=env, capture_output=True, text=True, timeout=120,
    )


class ProductionSettingsTests(SimpleTestCase):
    def test_sozlamalar_DEBUG_FALSE_bilan_yuklanadi(self):
        """
        ENG MUHIM TEKSHIRUV: sozlamalar yuklanmasa server ko'tarilmaydi
        va sayt umuman ochilmaydi.
        """
        result = run_in_prod("print('YUKLANDI')")

        self.assertIn('YUKLANDI', result.stdout, result.stderr[-2000:])
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_domen_CSRF_royxatiga_tushadi(self):
        """
        Domen ro'yxatda bo'lmasa har bir forma "CSRF Failed: Origin
        checking failed" bilan rad etiladi — paneldagi kirish ham.
        """
        result = run_in_prod(
            "from django.conf import settings\n"
            "print('|'.join(settings.CSRF_TRUSTED_ORIGINS))"
        )

        origins = result.stdout.strip().split('|')
        self.assertIn('https://oson.uz', origins)
        self.assertIn('https://www.oson.uz', origins)
        # Frontend manzili ustiga yozilmasligi kerak
        self.assertIn('https://oson.vercel.app', origins)

    def test_lokal_manzillar_productionga_otmaydi(self):
        result = run_in_prod(
            "from django.conf import settings\n"
            "print('|'.join(settings.CSRF_TRUSTED_ORIGINS + settings.CORS_ALLOWED_ORIGINS))"
        )

        self.assertNotIn('localhost', result.stdout)
        self.assertNotIn('127.0.0.1', result.stdout)

    def test_xavfsizlik_sozlamalari_yoqiladi(self):
        result = run_in_prod(
            "from django.conf import settings\n"
            "print(settings.SECURE_SSL_REDIRECT, settings.SESSION_COOKIE_SECURE, "
            "settings.CSRF_COOKIE_SECURE, settings.SECURE_HSTS_SECONDS)"
        )

        self.assertEqual(result.stdout.split(), ['True', 'True', 'True', '2592000'])

    def test_deploy_tekshiruvi_toza(self):
        """
        Django'ning o'z `check --deploy` tekshiruvi. Ogohlantirish
        bo'lsa — production sozlamasida kamchilik bor.
        """
        env = {**os.environ, **PROD_ENV}
        result = subprocess.run(
            [sys.executable, 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'],
            cwd=BASE_DIR, env=env, capture_output=True, text=True, timeout=120,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
