"""
Mavjud topshiriqlarni JavaScript deb belgilaydi.

NEGA KERAK: `Challenge.language` maydoni `python` standarti bilan
qo'shildi (platforma asosan Python o'rgatadi). Lekin bazadagi eski
topshiriqlar JavaScript uchun yozilgan — kodi `function sum(a, b) {...}`,
tavsifi "Console-da ... chiqaring". Ular avtomatik `python` bo'lib qolsa,
muharrir ularni Pyodide da ishga tushirib sintaksis xatosi berardi.

Faqat SHU migratsiya paytida mavjud yozuvlarga tegadi. Bundan keyin
yaratilgan topshiriqlar standart bo'yicha Python bo'ladi.
"""

from django.db import migrations


def mark_existing_as_javascript(apps, schema_editor):
    Challenge = apps.get_model('core', 'Challenge')
    Challenge.objects.update(language='javascript')


def noop(apps, schema_editor):
    """Orqaga qaytarish: til ma'lumoti yo'qoladi, tiklab bo'lmaydi."""


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_challenge_language'),
    ]

    operations = [
        migrations.RunPython(mark_existing_as_javascript, noop),
    ]
