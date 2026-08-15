"""
Dars videolarini uzatish
========================

UCH REJIM. Qaysi biri ishlatilishi SOZLAMAGA qarab hal qilinadi,
ko'rinishlarda `if` yozilmaydi:

    1. S3 / R2   -> imzolangan vaqtinchalik havola (production, bulut)
    2. nginx     -> X-Accel-Redirect (production, o'z serveri)
    3. Django    -> faylni o'zi uzatadi (faqat lokal ishlab chiqish)

NEGA BULUT KERAK BO'LIB QOLDI:

Railway va shunga o'xshash platformalarda fayl tizimi VAQTINCHALIK —
har deployda o'chadi. 5 GB video u yerda yashay olmaydi. Ustiga nginx
ham yo'q, ya'ni `X-Accel-Redirect` ishlamaydi va Django 5 GB faylni
o'zi uzatishga majbur bo'lardi: bitta tomoshabin bitta worker'ni
butun video davomida band qilib turardi.

IMZOLANGAN HAVOLA NIMA UCHUN:

Faylni ochiq qoldirish mumkin emas — havolani bir marta olgan odam uni
tarqatib yuborardi va obuna ma'nosini yo'qotardi. Imzolangan havola
qisqa muddat (standart 4 soat) amal qiladi va shu vaqtdan keyin
o'ladi. Huquq esa har safar Django tomonida QAYTA tekshiriladi —
havola faqat tekshiruvdan o'tgandan keyin beriladi.

BOTO3 IXTIYORIY: kutubxona o'rnatilmagan bo'lsa ham loyiha ishlaydi,
faqat bulut rejimi o'chiq bo'ladi. Shu sabab import funksiya ichida.
"""

import logging
import mimetypes

from django.conf import settings

logger = logging.getLogger(__name__)

#: Imzolangan havola necha soniya amal qiladi.
#: 4 soat — eng uzun dars ham bemalol tugaydi, lekin havola
#: tarqatilgan taqdirda ham ertasiga ishlamaydi.
DEFAULT_URL_TTL = 4 * 60 * 60


class VideoStorageError(Exception):
    """Sozlama xatosi — foydalanuvchiga emas, adminga."""


def is_cloud_enabled() -> bool:
    """Bulut ombori sozlanganmi."""
    return bool(
        getattr(settings, 'VIDEO_STORAGE_BUCKET', '')
        and getattr(settings, 'VIDEO_STORAGE_ACCESS_KEY', '')
        and getattr(settings, 'VIDEO_STORAGE_SECRET_KEY', '')
    )


def _client():
    """
    S3 mos klient.

    R2, Backblaze B2, MinIO — hammasi S3 API ni gapiradi, shuning
    uchun bitta klient yetadi. Farq faqat `endpoint_url` da.
    """
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:  # pragma: no cover — kutubxona bo'lmasa
        raise VideoStorageError(
            "boto3 o'rnatilmagan. `pip install boto3` yoki bulut rejimini o'chiring."
        ) from exc

    return boto3.client(
        's3',
        endpoint_url=getattr(settings, 'VIDEO_STORAGE_ENDPOINT', '') or None,
        aws_access_key_id=settings.VIDEO_STORAGE_ACCESS_KEY,
        aws_secret_access_key=settings.VIDEO_STORAGE_SECRET_KEY,
        region_name=getattr(settings, 'VIDEO_STORAGE_REGION', 'auto'),
        # SigV4 — R2 va yangi S3 mintaqalari uchun MAJBURIY.
        # Standart (SigV2) da imzo rad etiladi.
        config=Config(signature_version='s3v4'),
    )


def signed_url(key: str, ttl: int = DEFAULT_URL_TTL) -> str:
    """
    Faylga vaqtinchalik imzolangan havola.

    `key` — bucket ichidagi yo'l, masalan `lesson_videos/1-dars.mp4`.
    """
    if not is_cloud_enabled():
        raise VideoStorageError("Bulut ombori sozlanmagan.")

    return _client().generate_presigned_url(
        'get_object',
        Params={
            'Bucket': settings.VIDEO_STORAGE_BUCKET,
            'Key': key,
            # Brauzer videoni YUKLAB OLMASIN, ijro etsin
            'ResponseContentType': mimetypes.guess_type(key)[0] or 'video/mp4',
        },
        ExpiresIn=ttl,
    )


def upload(local_path, key: str, content_type: str = None) -> None:
    """Faylni bucketga yuklaydi. `migrate_videos` buyrug'i ishlatadi."""
    if not is_cloud_enabled():
        raise VideoStorageError("Bulut ombori sozlanmagan.")

    extra = {'ContentType': content_type or mimetypes.guess_type(key)[0] or 'video/mp4'}
    _client().upload_file(str(local_path), settings.VIDEO_STORAGE_BUCKET, key, ExtraArgs=extra)


def exists(key: str) -> bool:
    """Bucketda shunday fayl bormi."""
    if not is_cloud_enabled():
        return False

    from botocore.exceptions import ClientError

    try:
        _client().head_object(Bucket=settings.VIDEO_STORAGE_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def size(key: str):
    """Bucketdagi faylning hajmi (bayt). Topilmasa None."""
    if not is_cloud_enabled():
        return None

    from botocore.exceptions import ClientError

    try:
        head = _client().head_object(Bucket=settings.VIDEO_STORAGE_BUCKET, Key=key)
        return head['ContentLength']
    except ClientError:
        return None
