"""
Dars videolarini bulut omboriga ko'chiradi.

    python manage.py migrate_videos --dry-run     # avval ko'ring
    python manage.py migrate_videos

XAVFSIZ: lokal fayllar O'CHIRILMAYDI. Buyruq faqat NUSXA KO'CHIRADI.
5 GB ni qayta yuklash oson emas, shuning uchun o'chirish alohida,
ONGLI qadam bo'lishi kerak — `--delete-local` bilan va faqat bulutda
fayl borligi tasdiqlangandan keyin.

QAYTA ISHGA TUSHIRISH XAVFSIZ: bulutda allaqachon bor va hajmi mos
kelgan fayl o'tkazib yuboriladi. Ulanish uzilsa, buyruqni qaytadan
ishga tushirasiz va u qolganidan davom etadi.

BAZAGA TEGMAYDI: `video_file.name` o'zgarmaydi, chunki bulutdagi kalit
ham aynan shu yo'l. Ya'ni ko'chirishdan keyin hech qanday migratsiya
kerak emas va orqaga qaytarish ham oson — sozlamani bo'shatish yetadi.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import video_storage
from core.models import Lesson


class Command(BaseCommand):
    help = "Dars videolarini S3/R2 omboriga ko'chiradi"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help="Hech narsa yuklamaydi, faqat rejani ko'rsatadi")
        parser.add_argument('--limit', type=int, default=0,
                            help="Nechta fayl ko'chirilsin (0 = hammasi)")
        parser.add_argument(
            '--delete-local', action='store_true',
            help=(
                "Yuklangandan KEYIN lokal faylni o'chiradi. Faqat bulutda "
                "fayl borligi va hajmi mos kelgani tasdiqlangach o'chadi."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if not video_storage.is_cloud_enabled():
            raise CommandError(
                "Bulut ombori sozlanmagan.\n"
                "`.env` da to'ldiring: VIDEO_STORAGE_BUCKET, VIDEO_STORAGE_ENDPOINT,\n"
                "VIDEO_STORAGE_ACCESS_KEY, VIDEO_STORAGE_SECRET_KEY"
            )

        lessons = Lesson.objects.exclude(video_file='').exclude(video_file__isnull=True)
        if options['limit']:
            lessons = lessons[:options['limit']]

        lessons = list(lessons)
        if not lessons:
            self.stdout.write("Ko'chiriladigan video yo'q.")
            return

        self.stdout.write(f"Bucket : {settings.VIDEO_STORAGE_BUCKET}")
        self.stdout.write(f"Videolar: {len(lessons)}\n")

        stats = {'uploaded': 0, 'skipped': 0, 'missing': 0, 'failed': 0, 'deleted': 0}
        total_bytes = 0

        for lesson in lessons:
            key = lesson.video_file.name
            local = settings.MEDIA_ROOT / key

            if not local.exists():
                self.stdout.write(self.style.WARNING(f"  YO'Q      {key}"))
                stats['missing'] += 1
                continue

            local_size = local.stat().st_size
            remote_size = video_storage.size(key)

            if remote_size == local_size:
                self.stdout.write(f"  bor      {key}  ({local_size / 1024 / 1024:.0f} MB)")
                stats['skipped'] += 1
                self._maybe_delete(local, key, options, stats, dry_run)
                continue

            if dry_run:
                self.stdout.write(f"  yuklanadi {key}  ({local_size / 1024 / 1024:.0f} MB)")
                stats['uploaded'] += 1
                total_bytes += local_size
                continue

            try:
                video_storage.upload(local, key)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  XATO     {key}: {exc}"))
                stats['failed'] += 1
                continue

            self.stdout.write(
                self.style.SUCCESS(f"  yuklandi {key}  ({local_size / 1024 / 1024:.0f} MB)")
            )
            stats['uploaded'] += 1
            total_bytes += local_size
            self._maybe_delete(local, key, options, stats, dry_run)

        self.stdout.write("\nNatija")
        self.stdout.write(f"  Yuklandi   : {stats['uploaded']}")
        self.stdout.write(f"  Allaqachon : {stats['skipped']}")
        if stats['missing']:
            self.stdout.write(self.style.WARNING(f"  Fayl yo'q  : {stats['missing']}"))
        if stats['failed']:
            self.stdout.write(self.style.ERROR(f"  Xato       : {stats['failed']}"))
        if stats['deleted']:
            self.stdout.write(f"  O'chirildi : {stats['deleted']} (lokal)")
        self.stdout.write(f"  Hajm       : {total_bytes / 1024 / 1024 / 1024:.2f} GB")

        if dry_run:
            self.stdout.write(self.style.WARNING("\ndry-run: hech narsa yuklanmadi."))
        elif stats['uploaded'] or stats['skipped']:
            self.stdout.write(
                "\nEndi `.env` dagi VIDEO_STORAGE_* to'ldirilgan bo'lsa, "
                "videolar avtomatik bulutdan uzatiladi."
            )

    def _maybe_delete(self, local, key, options, stats, dry_run):
        """
        Lokal faylni o'chiradi — FAQAT bulutda hajmi mos fayl bo'lsa.

        Tekshiruvsiz o'chirish yarim yuklangan fayl qoldirib, videoni
        butunlay yo'qotishi mumkin edi.
        """
        if not options['delete_local'] or dry_run:
            return

        remote_size = video_storage.size(key)
        if remote_size != local.stat().st_size:
            self.stderr.write(
                self.style.WARNING(f"           {key}: hajm mos emas, o'chirilmadi")
            )
            return

        local.unlink()
        stats['deleted'] += 1
