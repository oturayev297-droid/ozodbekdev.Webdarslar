"""
Barcha darslar bepul.

Mavjud darslarning `is_free` bayrog'i yoqiladi va yangi darslar ham
bepul tug'iladi (default=True).

ORQAGA QAYTARILMAYDI: qaysi darslar avval pullik bo'lgani saqlanmaydi.
Pullik darslarga qaytish kerak bo'lsa, `seed_billing` yoki panel orqali
qayta belgilanadi.
"""

from django.db import migrations, models


def make_all_free(apps, schema_editor):
    Lesson = apps.get_model('core', 'Lesson')
    Lesson.objects.update(is_free=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_challenge_expected_output_challengeprogress'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lesson',
            name='is_free',
            field=models.BooleanField(
                default=True,
                help_text="Belgilansa, obunasiz ham ochiq bo'ladi",
                verbose_name='Bepul dars',
            ),
        ),
        migrations.RunPython(make_all_free, migrations.RunPython.noop),
    ]
