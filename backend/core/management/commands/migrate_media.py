"""
Dars rasmlari va avatarlarni bulut omboriga ko'chiradi.

    python manage.py migrate_media --dry-run
    python manage.py migrate_media

VIDEODAN ALOHIDA BUYRUQ. `migrate_videos` 5 GB ni soatlab ko'chiradi
va uzilishga qarshi qayta urinish mantig'i bor. Bu yerdagi fayllar esa
kilobaytlarda — ular uchun o'sha murakkablik ortiqcha, ustiga ikkalasi
bitta buyruqda bo'lsa, rasmni yangilash uchun ham 5 GB lik tekshiruvni
kutishga to'g'ri kelardi.

XAVFSIZ: lokal fayllar O'CHIRILMAYDI, faqat nusxa ko'chiriladi.
QAYTA ISHGA TUSHIRISH XAVFSIZ: bulutda bor va hajmi mos fayl
o'tkazib yuboriladi.

BAZAGA TEGMAYDI: bucketdagi kalit fayl yo'li bilan bir xil
(`lesson_images/sxema.png`), shuning uchun `MEDIA_STORAGE_CLOUD`
yoqilganda mavjud yozuvlar o'sha zahoti to'g'ri faylni topadi.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import video_storage

#: Qaysi papkalar ko'chiriladi.
#:
#: `lesson_videos` ATAYLAB YO'Q — u `migrate_videos` ning ishi.
DEFAULT_FOLDERS = ('lesson_images', 'profiles')


class Command(BaseCommand):
    help = "Dars rasmlari va avatarlarni S3/R2 omboriga ko'chiradi"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help="Hech narsa yuklamaydi, faqat rejani ko'rsatadi")
        parser.add_argument(
            '--folder', action='append', dest='folders', default=None,
            help=f"Qaysi papka (bir necha marta berish mumkin). Standart: {', '.join(DEFAULT_FOLDERS)}",
        )

    def handle(self, *args, **options):
        if not video_storage.is_cloud_enabled():
            raise CommandError(
                "Bulut ombori sozlanmagan.\n"
                "`.env` da to'ldiring: VIDEO_STORAGE_BUCKET, VIDEO_STORAGE_ENDPOINT,\n"
                "VIDEO_STORAGE_ACCESS_KEY, VIDEO_STORAGE_SECRET_KEY"
            )

        folders = options['folders'] or list(DEFAULT_FOLDERS)
        dry_run = options['dry_run']

        self.stdout.write(f"Bucket : {settings.VIDEO_STORAGE_BUCKET}")
        self.stdout.write(f"Papkalar: {', '.join(folders)}\n")

        stats = {'uploaded': 0, 'skipped': 0, 'failed': 0}

        for folder in folders:
            root = settings.MEDIA_ROOT / folder
            if not root.is_dir():
                self.stdout.write(self.style.WARNING(f"  papka yo'q: {folder}"))
                continue

            # Bulutdagi ro'yxat papka bo'yicha BIR MARTA olinadi —
            # har fayl uchun alohida so'rov yubormaslik uchun.
            remote_sizes = video_storage.list_sizes(prefix=f'{folder}/')

            for local in sorted(root.rglob('*')):
                if not local.is_file():
                    continue

                # Kalit — MEDIA_ROOT ga NISBATAN yo'l va u har doim
                # `/` bilan yoziladi: Windows'dagi `\` bucketda
                # boshqa fayl nomini bildirardi.
                key = local.relative_to(settings.MEDIA_ROOT).as_posix()
                local_size = local.stat().st_size

                if remote_sizes.get(key) == local_size:
                    self.stdout.write(f"  bor      {key}")
                    stats['skipped'] += 1
                    continue

                if dry_run:
                    self.stdout.write(f"  yuklanadi {key}  ({local_size / 1024:.0f} KB)")
                    stats['uploaded'] += 1
                    continue

                try:
                    video_storage.upload(local, key)
                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f"  XATO     {key}: {exc}"))
                    stats['failed'] += 1
                    continue

                self.stdout.write(
                    self.style.SUCCESS(f"  yuklandi {key}  ({local_size / 1024:.0f} KB)")
                )
                stats['uploaded'] += 1

        self.stdout.write("\nNatija")
        self.stdout.write(f"  Yuklandi   : {stats['uploaded']}")
        self.stdout.write(f"  Allaqachon : {stats['skipped']}")
        if stats['failed']:
            self.stdout.write(self.style.ERROR(f"  Xato       : {stats['failed']}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("\ndry-run: hech narsa yuklanmadi."))
