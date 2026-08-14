"""
Panel kontekst protsessori
==========================

Yon menyudagi ikkita hisoblagich: javob kutayotgan to'lovlar va
qoralama testlar.

IKKI QAT'IY SHART:

1. FAQAT XODIM UCHUN. Anonim va oddiy o'quvchining har bir sahifasida
   bu so'rovlar ishlab tursa — bekorga yuk. Shuning uchun birinchi
   qatorning o'zidayoq chiqib ketamiz.

2. FAQAT `/panel/` ICHIDA. Kontekst protsessori BARCHA shablonlarga
   qo'shiladi, demak xodim sayt bo'ylab yurganda ham har sahifada
   ikkita qo'shimcha so'rov ketardi. Manzil bo'yicha ham cheklaymiz.
"""

from billing.models import PaymentRequest, RequestStatus
from core.models import Quiz

#: Hisoblagichlar faqat shu prefiksdagi sahifalarda hisoblanadi
PANEL_PREFIX = '/panel/'

EMPTY = {'panel_awaiting': 0, 'panel_drafts': 0}


def panel_badges(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated or not user.is_staff:
        return EMPTY

    if not request.path.startswith(PANEL_PREFIX):
        return EMPTY

    return {
        # Eng shoshilinchi: o'quvchi pulni yuborgan, javob kutmoqda
        'panel_awaiting': PaymentRequest.objects.filter(
            status=RequestStatus.RECEIPT_UPLOADED
        ).count(),
        'panel_drafts': Quiz.objects.filter(is_published=False).count(),
    }
