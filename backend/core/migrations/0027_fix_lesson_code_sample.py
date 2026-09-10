"""
"Python Lesson 2" darsining kod namunasini tuzatish.

Namuna ishga tushirilsa yiqilardi:
  * lug'at `User` deb e'lon qilingan, keyin esa `users` deb ishlatilgan
    -> NameError;
  * `For` katta harf bilan -> SyntaxError;
  * blok ichida 6 bo'shliq va `:` oldida ortiqcha bo'shliq, "SUhrob".

O'quvchi namunani muharrirga ko'chirib ishlatsa, xatoni o'zidan
izlardi — namunaning o'zi xato ekanini bilmay.

ADMIN O'ZGARTIRGAN NAMUNAGA TEGILMAYDI: faqat kod hali aynan o'sha
xato holatda bo'lsa almashtiriladi. Tuzatilgan kod
`core/fixtures/content.json` ga ham shu yerdan yozilgan.
"""

from django.db import migrations

LESSON_ID = 31

BROKEN = (
    "User={1:'Ozodbek',2:'SUhrob',3:'Yurist',4:'Shifokor'}\r\n\r\n"
    "For value in users.values() :\r\n      print(value)\r\n\r\n"
    "for key in users.keys():\r\n    print(key)\r\n\r\n"
    "for key, value in users.items():\r\n    print(key, value)"
)

FIXED = (
    "users = {1: 'Ozodbek', 2: 'Suhrob', 3: 'Yurist', 4: 'Shifokor'}\n\n"
    "for value in users.values():\n    print(value)\n\n"
    "for key in users.keys():\n    print(key)\n\n"
    "for key, value in users.items():\n    print(key, value)"
)


def _normalize(code: str) -> str:
    return (code or '').replace('\r\n', '\n').strip()


def fix_code_sample(apps, schema_editor):
    Lesson = apps.get_model('core', 'Lesson')

    lesson = Lesson.objects.filter(pk=LESSON_ID).first()
    if lesson and _normalize(lesson.practice_code) == _normalize(BROKEN):
        lesson.practice_code = FIXED
        lesson.save(update_fields=['practice_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_fix_quiz_questions'),
    ]

    operations = [
        migrations.RunPython(fix_code_sample, migrations.RunPython.noop),
    ]
