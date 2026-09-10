"""
Kirish darslarining kod namunalarini tuzatish.

  * "JavaScript Lesson 1" va "React Lesson 1" — kod namunasi o'rnida
    Python kodi turardi: `print("Hello")`. JavaScript'da `print` yo'q —
    namuna ko'chirilsa xato berardi.
  * "Python darslari Kirish" — kod maydonida kod emas, YouTube pleylist
    havolasi turardi. Havola YO'QOLMAYDI: u dars matniga bosiladigan
    havola bo'lib ko'chadi, kod maydoniga esa birinchi Python dasturi
    yoziladi.

ADMIN O'ZGARTIRGAN QIYMATGA TEGILMAYDI: har bir maydon faqat hali
aynan o'sha eski holatda bo'lsa almashtiriladi. Yangi qiymatlar
`core/fixtures/content.json` ga ham shu yerdan yozilgan.
"""

from django.db import migrations

PLAYLIST_URL = "https://youtu.be/_f8cpjAz0sw?list=PLOvS2OkP87tSfos3rmPAhg9FqFDhbOcr1"

INTRO_THEORY = (
    "Kirish \r\n\r\nDasutrlash asoslari darsimizni boshlaymiz. \r\n"
    "Darsning maqsadi nima? \r\nNima uchun aynan Pyhton?"
)

#: (dars pk, maydon, eski qiymat, yangi qiymat)
FIXES = [
    (29, 'practice_code', 'print("Hello")', (
        "// Natija brauzer konsolida ko'rinadi (F12 -> Console)\n"
        'console.log("Salom, JavaScript!");\n'
        "\n"
        "let yosh = 20;\n"
        "console.log(yosh);\n"
        'console.log(typeof yosh); // "number"'
    )),
    (28, 'practice_code', 'print("Hello")', (
        "// Birinchi komponent: funksiya JSX qaytaradi\n"
        "function Salom() {\n"
        "  return <h1>Salom, React!</h1>;\n"
        "}\n"
        "\n"
        "export default Salom;"
    )),
    (32, 'practice_code',
     f"{PLAYLIST_URL}\r\nBU onlayn darsning video silkasi", (
        "# Birinchi dasturimiz\n"
        'print("Salom, dunyo!")'
    )),
    (32, 'theory', INTRO_THEORY,
     f"{INTRO_THEORY}\r\n\r\n[Kursning YouTube'dagi video pleylisti]({PLAYLIST_URL})"),
]


def _normalize(value: str) -> str:
    return (value or '').replace('\r\n', '\n').strip()


def fix_samples(apps, schema_editor):
    Lesson = apps.get_model('core', 'Lesson')

    for lesson_id, field, old, new in FIXES:
        lesson = Lesson.objects.filter(pk=lesson_id).first()
        if lesson and _normalize(getattr(lesson, field)) == _normalize(old):
            setattr(lesson, field, new)
            lesson.save(update_fields=[field])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_fix_lesson_code_sample'),
    ]

    operations = [
        migrations.RunPython(fix_samples, migrations.RunPython.noop),
    ]
