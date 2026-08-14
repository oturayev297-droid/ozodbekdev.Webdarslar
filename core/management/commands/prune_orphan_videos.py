"""
Hech qaysi darsga bog'lanmagan video fayllarni topadi.

Admin panelda video qayta yuklanganda Django eski faylni O'CHIRMAYDI —
yangi nom bilan yonига qo'yadi (`1-dars_Xm098yg.mp4`). Vaqt o'tib bu
fayllar yig'ilib, diskni bekorga egallaydi.

XAVFSIZLIK: standart holda HECH NARSA O'CHIRILMAYDI — faqat ro'yxat
ko'rsatiladi. O'chirish uchun `--delete` kerak, va u ham tasdiq so'raydi.
Video fayllar backup'da bo'lmasa qaytarib bo'lmaydi.

    python manage.py prune_orphan_videos            # faqat ko'rsatadi
    python manage.py prune_orphan_videos --delete   # o'chiradi (tasdiq bilan)
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Lesson


class Command(BaseCommand):
    help = "Darsga bog'lanmagan video fayllarni topadi (standart holda o'chirmaydi)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete', action='store_true',
            help="Topilgan fayllarni o'chiradi (tasdiq so'raydi)",
        )
        parser.add_argument(
            '--yes', action='store_true',
            help="Tasdiqni so'ramaydi. Faqat skriptlar uchun.",
        )

    def handle(self, *args, **options):
        folder = Path(settings.MEDIA_ROOT) / 'lesson_videos'
        if not folder.is_dir():
            self.stdout.write(self.style.WARNING(f"Papka yo'q: {folder}"))
            return

        # Bazada ishlatilayotgan fayl nomlari
        used = set()
        for lesson in Lesson.objects.exclude(video_file='').exclude(video_file=None):
            if lesson.video_file:
                used.add(Path(lesson.video_file.name).name)

        on_disk = {f.name: f for f in folder.iterdir() if f.is_file()}
        orphans = sorted(set(on_disk) - used)

        self.stdout.write(f"Bazada ishlatilgan : {len(used)}")
        self.stdout.write(f"Diskda             : {len(on_disk)}")
        self.stdout.write(f"Bog'lanmagan       : {len(orphans)}")

        if not orphans:
            self.stdout.write(self.style.SUCCESS("\nOrtiqcha fayl yo'q."))
            return

        total = 0
        self.stdout.write("")
        for name in orphans:
            size = on_disk[name].stat().st_size
            total += size
            self.stdout.write(f"  {size / 1024 / 1024:8.1f} MB  {name}")

        gb = total / 1024 / 1024 / 1024
        self.stdout.write(self.style.WARNING(f"\nJami: {gb:.2f} GB"))

        if not options['delete']:
            self.stdout.write(
                "\nHech narsa o'chirilmadi. O'chirish uchun: "
                "python manage.py prune_orphan_videos --delete"
            )
            return

        if not options['yes']:
            self.stdout.write(self.style.ERROR(
                f"\nDIQQAT: {len(orphans)} ta fayl ({gb:.2f} GB) butunlay o'chiriladi.\n"
                "Backup borligiga ishonch hosil qiling — qaytarib bo'lmaydi."
            ))
            answer = input("Davom etilsinmi? [ha/yo'q]: ").strip().lower()
            if answer not in ('ha', 'yes', 'y'):
                self.stdout.write("Bekor qilindi.")
                return

        removed = 0
        freed = 0
        for name in orphans:
            path = on_disk[name]
            try:
                size = path.stat().st_size
                path.unlink()
                removed += 1
                freed += size
            except OSError as exc:
                self.stdout.write(self.style.ERROR(f"  O'chirilmadi {name}: {exc}"))

        self.stdout.write(self.style.SUCCESS(
            f"\n{removed} ta fayl o'chirildi, {freed / 1024 / 1024 / 1024:.2f} GB bo'shadi."
        ))
