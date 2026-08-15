"""
`core` ko'rinishlari — FAQAT FAYL UZATISH.

Eski o'quvchi sahifalari (landing, darslar, dashboard, muharrir,
testlar, profil, autentifikatsiya) OLIB TASHLANDI: ularning o'rnini
React frontend egalladi va mantiq `api/` ga ko'chdi.

BU YERDA IKKITA KO'RINISH QOLDI va ikkalasi ham HTML emas, FAYL
qaytaradi:

  lesson_video     — 5 GB video. Uni React qayta yoza olmaydi:
                     fayl uzatish serverning ishi. Huquq shu yerda
                     tekshiriladi va faqat undan keyin havola
                     beriladi.

  certificate_pdf  — PDF `reportlab` bilan serverda chiziladi.
                     Brauzerda emas, chunki mazmun `Certificate`
                     yozuvida muzlatilgan va u ishonchli bo'lishi
                     kerak.

Panel (`/panel/`) o'z ko'rinishlariga ega va u SERVER TOMONDA
render qilinishda davom etadi — u faqat xodimlar uchun.
"""

import logging
import mimetypes

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect

from billing.gating import can_access_lesson, paywall

from . import certificates, video_storage
from .approval import approval_required
from .models import Certificate, Lesson

logger = logging.getLogger(__name__)


@approval_required
@login_required
def lesson_video(request, lesson_id):
    """
    Dars videosini FAQAT huquqi bor foydalanuvchiga uzatadi.

    UCHTA REJIM, sozlamaga qarab tanlanadi:

      1. Bulut (S3/R2) -> imzolangan vaqtinchalik havolaga yo'naltiradi
      2. nginx         -> X-Accel-Redirect, faylni nginx uzatadi
      3. Django        -> faylni o'zi uzatadi (FAQAT lokal)

    Uchalasida ham HUQUQ SHU YERDA, Django tomonida tekshiriladi.
    Havola faqat tekshiruvdan keyin beriladi.

    3-rejim productionda ishlatilmaydi: 5 GB faylni uzatayotgan
    Django worker'i butun video davomida band bo'lib qoladi.
    """
    lesson = get_object_or_404(Lesson, id=lesson_id)

    # DARVOZA: bepul dars hammaga, qolgani faol obunaga.
    if not can_access_lesson(request.user, lesson):
        return paywall(request, "Bu dars videosi obuna bilan ochiladi.")

    if not lesson.video_file:
        raise Http404("Bu darsda video yo'q")

    name = lesson.video_file.name

    # ── 1. Bulut ombori ──
    if video_storage.is_cloud_enabled():
        try:
            url = video_storage.signed_url(name)
        except video_storage.VideoStorageError:
            logger.exception("Imzolangan havola olinmadi: %s", name)
            raise Http404("Video hozircha mavjud emas")
        # 302: brauzer to'g'ridan-to'g'ri omborga boradi va Django
        # trafikda umuman qatnashmaydi.
        return redirect(url)

    # ── 2. nginx ──
    if settings.USE_X_ACCEL_REDIRECT:
        response = HttpResponse()
        # nginx da: location /protected/ { internal; alias /path/to/media/; }
        response['X-Accel-Redirect'] = f'/protected/{name}'
        response['Content-Type'] = (
            mimetypes.guess_type(name)[0] or 'application/octet-stream'
        )
        del response['Content-Length']
        return response

    # ── 3. Django (faqat lokal) ──
    try:
        return FileResponse(lesson.video_file.open('rb'), content_type='video/mp4')
    except FileNotFoundError:
        logger.error("Video fayl diskda topilmadi: %s", name)
        raise Http404("Video fayl topilmadi")


@approval_required
@login_required
def certificate_pdf(request, code):
    """
    Sertifikat PDF si.

    Faqat EGASI yoki admin yuklab oladi. Ommaviy tekshirish uchun
    alohida sahifa bor (`verify_certificate`) — u PDF bermaydi, chunki
    kodni bilgan har kim boshqaning hujjatini yuklab olmasligi kerak.
    """
    certificate = get_object_or_404(
        Certificate.objects.select_related('quiz', 'user'), code=code
    )
    if certificate.user_id != request.user.id and not request.user.is_staff:
        raise Http404("Sertifikat topilmadi")

    # TEKSHIRISH SAHIFASI FRONTENDDA. PDF dagi QR/havola ish
    # beruvchini o'sha yerga olib boradi, backendga emas — backend
    # unga ko'rsatadigan sahifa yo'q.
    #
    # `FRONTEND_URL` sozlanmagan bo'lsa API manzili ishlatiladi: u
    # JSON qaytaradi, lekin hech bo'lmasa tekshirish IMKONI qoladi.
    base = getattr(settings, 'FRONTEND_URL', '')
    if base:
        verify_url = f"{base}/sertifikat-tekshirish?code={certificate.code}"
    else:
        verify_url = request.build_absolute_uri(
            f'/api/v1/certificates/verify/?code={certificate.code}'
        )
    pdf = certificates.build_pdf(certificate, verify_url=verify_url)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="{certificates.filename_for(certificate)}"'
    )
    return response
