"""
Kontentdagi imlo xatolari.

Dars matnlari, test nomlari, test savollari va loyiha tavsifidagi
xatolar: "Dasutrlash", "Pyhton", "Brauserda", "Fcuntion expresson",
"arcqali", "malumot" va boshqalar (to'liq ro'yxat — `FIXES`).

Butun matn emas, faqat shu SO'ZLAR almashtiriladi — shuning uchun
admin matnni panelda o'zgartirgan bo'lsa ham xavfsiz: xato so'z
bo'lmasa hech narsa o'zgarmaydi, qolgan matnga tegilmaydi. Takroriy
ishga tushirish ham hech narsani buzmaydi.

Yozuvlar pk bo'yicha topiladi — ular `content.json` dan yuklangan va
lokal hamda production'da bir xil.
"""

from django.db import migrations

#: (model, pk, maydon, {xato: to'g'ri})
FIXES = [
    ('Lesson', 32, 'theory', {"Dasutrlash": "Dasturlash", "Pyhton": "Python"}),
    ('Lesson', 74, 'theory', {"Brauserda": "Brauzerda"}),
    ('Lesson', 79, 'theory', {"ishlatilinadigan": "ishlatiladigan"}),
    ('Lesson', 98, 'theory', {"decloration": "declaration",
                              "Fcuntion expresson": "Function expression"}),
    ('Lesson', 99, 'theory', {"Parametorlar": "Parametrlar"}),
    ('Quiz', 10, 'title', {"ro'yhat": "ro'yxat"}),
    ('Quiz', 11, 'title', {"Ro'yhat": "Ro'yxat"}),
    ('Question', 284, 'text', {"qoyiladi": "qo'yiladi"}),
    ('Question', 335, 'text', {"arcqali": "orqali"}),
    ('Question', 342, 'text', {"malumot": "ma'lumot"}),
    ('Question', 402, 'text', {"sozini": "so'zini"}),
    ('Project', 4, 'description', {"daxshatli": "dahshatli"}),
]


def fixed_value(model: str, pk: int, field: str, text: str) -> str:
    """`text` ga shu yozuv/maydon uchun ro'yxatdagi tuzatishlarni qo'llaydi."""
    for fix_model, fix_pk, fix_field, replacements in FIXES:
        if (fix_model, fix_pk, fix_field) == (model, pk, field):
            for wrong, right in replacements.items():
                text = text.replace(wrong, right)
    return text


def fix_typos(apps, schema_editor):
    for model_name, pk, field, _ in FIXES:
        obj = apps.get_model('core', model_name).objects.filter(pk=pk).first()
        if obj is None:
            continue
        current = getattr(obj, field) or ''
        fixed = fixed_value(model_name, pk, field, current)
        if fixed != current:
            setattr(obj, field, fixed)
            obj.save(update_fields=[field])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_fix_intro_code_samples'),
    ]

    operations = [
        migrations.RunPython(fix_typos, migrations.RunPython.noop),
    ]
