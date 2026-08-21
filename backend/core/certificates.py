"""
Sertifikat generatsiyasi
========================

Sertifikat 80% va undan yuqori ball olganda beriladi. Chegara shu faylda —
dashboard'dagi hisob ham shu qiymatdan o'qiydi, ikki joyda takrorlanmasin.

PDF `reportlab` bilan xotirada chiziladi va diskka SAQLANMAYDI: fayl har
so'rovda qayta yaratiladi. Sababi — mazmun `Certificate` yozuvida
allaqachon muzlatilgan, PDF esa uning ko'rinishi. Diskda saqlansa 5 GB
video ustiga yana minglab fayl qo'shilardi va ular bilan bog'liq backup
muammosi paydo bo'lardi.

TEKSHIRISH: har sertifikatda tasodifiy `code` va uni ochadigan ommaviy
havola bor. Ish beruvchi kodni kiritib sertifikat haqiqiyligini
tekshiradi — login talab qilinmaydi.
"""

import io
import logging
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from .models import Certificate, QuizResult

logger = logging.getLogger(__name__)

#: Sertifikat beriladigan eng kichik ball
PASS_SCORE = 80

#: Kod uzunligi (belgilar). 8 baytdan 16 belgilik hex chiqadi —
#: taxmin qilib topish amalda imkonsiz.
CODE_BYTES = 8


def generate_code() -> str:
    """
    Tasodifiy, taxmin qilinmaydigan kod.

    Ketma-ket ID ISHLATILMAYDI: /verify/1, /verify/2 deb yurib butun
    bazani sanab chiqib bo'lardi.
    """
    return secrets.token_hex(CODE_BYTES).upper()


def issue_for_result(result: QuizResult):
    """
    Natija bo'yicha sertifikat beradi (yoki mavjudini qaytaradi).

    IDEMPOTENT: `unique_together (user, quiz)` — bitta test uchun bitta
    sertifikat. Test qayta topshirilib ball oshsa, sertifikatdagi ball
    ATAYLAB o'zgarmaydi: berilgan hujjat keyin qayta yozilmaydi.
    """
    if result.score_percentage < PASS_SCORE:
        return None

    existing = Certificate.objects.filter(user=result.user, quiz=result.quiz).first()
    if existing:
        return existing

    lesson = result.quiz.lesson
    category = getattr(getattr(lesson, 'module', None), 'category', None)
    profile = getattr(result.user, 'profile', None)

    # Kod to'qnashuvi amalda bo'lmaydi, lekin unique cheklov bor —
    # bir necha marta urinib ko'ramiz va jimgina yiqilmaymiz.
    for _ in range(5):
        try:
            with transaction.atomic():
                certificate = Certificate.objects.create(
                    code=generate_code(),
                    user=result.user,
                    quiz=result.quiz,
                    score_percentage=result.score_percentage,
                    full_name=(profile.full_name if profile else '') or '',
                    quiz_title=result.quiz.title,
                    category_name=category.name if category else '',
                )
            logger.info(
                "[SERTIFIKAT] %s berildi: %s (%s%%)",
                certificate.code, result.user.username, result.score_percentage,
            )
            return certificate
        except IntegrityError:
            # Ikki xil sabab bo'lishi mumkin: kod to'qnashdi yoki boshqa
            # so'rov shu payt sertifikat yaratdi. Ikkinchisida mavjudini
            # qaytaramiz.
            existing = Certificate.objects.filter(user=result.user, quiz=result.quiz).first()
            if existing:
                return existing

    logger.error("[SERTIFIKAT] Kod generatsiya qilinmadi: user=%s", result.user.pk)
    return None


# ==========================================================================
# PDF
# ==========================================================================


def build_pdf(certificate: Certificate, verify_url: str = "") -> bytes:
    """
    Sertifikat PDF sini xotirada chizadi.

    Shrift: reportlab ning ichki Helvetica si. Tashqi shrift fayli
    ATAYLAB ishlatilmaydi — u repozitoriyga qo'shilishi, litsenziyasi
    tekshirilishi va deploy da mavjud bo'lishi kerak bo'lardi.
    O'zbek lotin alifbosi Latin-1 ga sig'adi, shuning uchun ichki shrift
    yetarli.
    """
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as pdf_canvas

    width, height = landscape(A4)
    buffer = io.BytesIO()
    c = pdf_canvas.Canvas(buffer, pagesize=landscape(A4))
    c.setTitle(f"Sertifikat {certificate.code}")
    c.setAuthor("ozodbekdev.uz")

    ink = HexColor("#0f172a")
    accent = HexColor("#0ea5e9")
    muted = HexColor("#64748b")
    teal = HexColor("#2dd4bf")

    # ── Fon ──
    c.setFillColor(HexColor("#f8fafc"))
    c.rect(0, 0, width, height, stroke=0, fill=1)

    # Yuqori va pastdagi rangli chiziqlar
    c.setFillColor(accent)
    c.rect(0, height - 8 * mm, width, 8 * mm, stroke=0, fill=1)
    c.setFillColor(teal)
    c.rect(0, 0, width, 4 * mm, stroke=0, fill=1)

    # Ramka
    c.setStrokeColor(HexColor("#cbd5e1"))
    c.setLineWidth(0.8)
    c.rect(14 * mm, 12 * mm, width - 28 * mm, height - 30 * mm, stroke=1, fill=0)

    # ── Sarlavha ──
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, height - 30 * mm, "O Z O D B E K D E V . U Z")

    c.setFillColor(muted)
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, height - 36 * mm, "ONLAYN TA'LIM PLATFORMASI")

    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(width / 2, height - 55 * mm, "SERTIFIKAT")

    c.setStrokeColor(accent)
    c.setLineWidth(2)
    c.line(width / 2 - 30 * mm, height - 60 * mm, width / 2 + 30 * mm, height - 60 * mm)

    # ── Egasi ──
    c.setFillColor(muted)
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, height - 74 * mm, "Ushbu sertifikat")

    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width / 2, height - 88 * mm, _fit(certificate.holder_name, 34))

    c.setFillColor(muted)
    c.setFont("Helvetica", 10)
    c.drawCentredString(
        width / 2, height - 99 * mm,
        "nomiga quyidagi kursni muvaffaqiyatli yakunlagani uchun berildi",
    )

    # ── Kurs ──
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 113 * mm, _fit(certificate.quiz_title, 52))

    if certificate.category_name:
        c.setFillColor(muted)
        c.setFont("Helvetica", 10)
        c.drawCentredString(
            width / 2, height - 121 * mm, f"Yo'nalish: {certificate.category_name}"
        )

    # ── Pastdagi ma'lumotlar ──
    # `base` ataylab 50mm: 34mm da bo'lganda kurs nomi bilan pastdagi
    # maydonlar orasida katta bo'sh joy qolib, varaq pastga og'ib
    # ko'rinardi.
    left = 30 * mm
    right = width - 30 * mm
    base = 50 * mm

    # Pastdagi blokni ajratuvchi ingichka chiziq
    c.setStrokeColor(HexColor("#e2e8f0"))
    c.setLineWidth(0.7)
    c.line(left, base + 16 * mm, right, base + 16 * mm)

    def field(x, label, value, align="left"):
        c.setFillColor(muted)
        c.setFont("Helvetica", 8)
        draw = c.drawString if align == "left" else c.drawRightString
        draw(x, base + 8 * mm, label)
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 11)
        draw(x, base + 2 * mm, value)

    field(left, "NATIJA", f"{certificate.score_percentage}%")
    field(left + 45 * mm, "BERILGAN SANA", timezone.localtime(certificate.issued_at).strftime("%d.%m.%Y"))
    field(right, "SERTIFIKAT KODI", certificate.code, align="right")

    # Imzo chizig'i
    c.setStrokeColor(HexColor("#cbd5e1"))
    c.setLineWidth(0.7)
    c.line(width / 2 - 25 * mm, base + 6 * mm, width / 2 + 25 * mm, base + 6 * mm)
    c.setFillColor(muted)
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, base + 1 * mm, "Platforma rahbari")

    # ── Tekshirish havolasi ──
    if verify_url:
        c.setFillColor(muted)
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(
            width / 2, 30 * mm,
            f"Haqiqiyligini tekshirish: {verify_url}",
        )

    if not certificate.is_valid:
        # Bekor qilingan sertifikat PDF da ham ko'rinib turishi kerak
        c.saveState()
        c.setFillColor(HexColor("#ef4444"))
        c.setFont("Helvetica-Bold", 60)
        c.translate(width / 2, height / 2)
        c.rotate(30)
        c.drawCentredString(0, 0, "BEKOR QILINGAN")
        c.restoreState()

    c.showPage()
    c.save()
    return buffer.getvalue()


def _fit(text: str, limit: int) -> str:
    """Uzun matnni qisqartiradi — chiziq chetidan chiqib ketmasin."""
    text = (text or '').strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def filename_for(certificate: Certificate) -> str:
    safe = "".join(
        ch if ch.isalnum() or ch in "-_" else "_"
        for ch in (certificate.holder_name or "sertifikat")
    )
    return f"sertifikat_{safe}_{certificate.code}.pdf"
