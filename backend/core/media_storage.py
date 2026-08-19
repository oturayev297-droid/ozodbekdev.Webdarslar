"""
Rasm va avatarlarni bulutda saqlash
===================================

NEGA KERAK BO'LDI

Railway'da fayl tizimi VAQTINCHALIK: har deployda konteyner yangidan
quriladi va oldingi konteynerga yozilgan hamma narsa yo'qoladi. Ya'ni
panel orqali yuklangan dars rasmi yoki o'quvchi qo'ygan avatar
birinchi yangilanishdayoq g'oyib bo'lardi — bazada yozuv qoladi,
faylning o'zi yo'q. Ustiga productionda `/media/` umuman uzatilmaydi
(`stitch_backend/urls.py` da u faqat `DEBUG` da ochiladi), shuning
uchun rasm yuklangan kunning o'zida ham ko'rinmasdi.

Videolar buni allaqachon hal qilgan (`core.video_storage`). Bu modul
o'sha yechimni QOLGAN fayllarga yoyadi: Django'ning standart fayl
ombori o'rniga shu sinf qo'yiladi va `ImageField` ning o'zi bulutga
yozadi. Model, forma va serializerlarga TEGILMAYDI — ular `.url` va
`.save()` ni qanday ishlatgan bo'lsa, shundayligicha qoladi.

QAYSI HOLATDA YOQILADI

`MEDIA_STORAGE_CLOUD=True` bo'lganda va bulut kalitlari to'ldirilganda
(`settings.py` ga qarang). Bayroq ATAYLAB alohida: lokal ishlab
chiqishda va testlarda kalitlar `.env` da bo'lsa ham fayllar diskda
qolishi kerak, aks holda har test ishga tushganda tarmoqqa chiqilar va
bucket sinov fayllari bilan to'lib ketardi.

HAVOLA IMZOLANADI

Bucket ochiq emas, shuning uchun `url()` imzolangan vaqtinchalik
havola qaytaradi. Rasm uchun bu videodagidek qat'iy himoya emas —
qiymati shundaki, bucketni ochiq qilmaslik hamma fayl uchun bitta
qoida bo'lib qoladi va kelajakda "bu papkani ochib qo'ygan edik" degan
teshik paydo bo'lmaydi.
"""

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

from core import video_storage

#: Rasm havolasi shuncha soniya amal qiladi.
#:
#: Videonikidan (4 soat) UZUNROQ, chunki xavf boshqacha: rasm
#: darsning kichik bo'lagi, videosi esa darsning o'zi. Sahifa uzoq
#: ochiq turganda havola eskirib, rasmlar "singan" bo'lib qolmasin.
IMAGE_URL_TTL = 24 * 60 * 60


@deconstructible
class CloudMediaStorage(Storage):
    """
    S3 mos ombor (Cloudflare R2, AWS S3, Backblaze B2).

    Django `Storage` dan faqat quyidagi metodlar talab qilinadi.
    Qolganini (`save`, `generate_filename`) asosiy sinf o'zi bajaradi
    va u `exists()` orqali nomlar to'qnashuvini ham hal qiladi — ya'ni
    bir xil nomli ikkinchi rasm eskisini BOSIB KETMAYDI, unga
    tasodifiy qo'shimcha qo'yiladi.
    """

    def _key(self, name):
        """
        Fayl nomini bucket KALITIGA aylantiradi.

        S3 da papka yo'q — `/` shunchaki nomning bir qismi. Windows'da
        esa Django nomlarni `os.path` bilan quradi va nomlar
        to'qnashganda `lesson_images\\sxema_a1b2c3.png` chiqib
        qoladi. Shunday kalit bucketga tushsa, fayl boshqa nom bilan
        yotib qolar va lokalda yuklangan rasm serverdan hech qachon
        topilmasdi.
        """
        return name.replace('\\', '/')

    def get_available_name(self, name, max_length=None):
        # Asosiy sinf nomni `os.path` bilan quradi va Windows'da
        # teskari chiziq qo'yadi. Kalitni SHU YERDA to'g'rilaymiz:
        # shunda bazaga yoziladigan nom ham, bucketdagi kalit ham
        # bir xil bo'ladi.
        return self._key(super().get_available_name(name, max_length))

    def _open(self, name, mode='rb'):
        if 'w' in mode:
            # Yozish `_save` orqali. Bu yerda ochiq qoldirilsa,
            # fayl xotirada o'zgartirilib, bucketga hech qachon
            # qaytarilmasdi.
            raise ValueError("Bulut omborida fayl yozish uchun ochilmaydi.")

        return ContentFile(video_storage.read(self._key(name)), name=name)

    def _save(self, name, content):
        key = self._key(name)
        video_storage.save_fileobj(content, key)
        # Bazaga YOZILADIGAN nom. U bucketdagi kalit bilan bir xil —
        # shu sabab omborni almashtirish uchun migratsiya kerak emas.
        return key

    def exists(self, name):
        return video_storage.exists(self._key(name))

    def delete(self, name):
        video_storage.delete(self._key(name))

    def size(self, name):
        return video_storage.size(self._key(name)) or 0

    def url(self, name):
        return video_storage.signed_url(self._key(name), ttl=IMAGE_URL_TTL)
