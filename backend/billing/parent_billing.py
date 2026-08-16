"""
Ota-ona obunasi va farzand uchun to'lov.

IKKI XIL TO'LOV BOR VA ULAR ARALASHTIRILMAYDI:

  1. OTA-ONANING O'Z OBUNASI — farzand hisobotini ko'rish uchun.
     Tarifi alohida (`PARENT_MONTHLY`), narxi ham alohida.

  2. FARZAND UCHUN TO'LOV — ota-ona bolasining darslarini ochadi.
     Bu o'quvchi tarifidagi oddiy to'lov, faqat so'rovni ota-ona
     boshlaydi. Pul o'quvchining obunasiga tushadi.

Ikkalasini bir joyda hisoblash mumkin emas edi: birinchisida
foydalanuvchi ham to'lovchi ham oladigan odam, ikkinchisida esa
to'lovchi bir kishi, oladigan boshqa. Hisobot uchun ham farqi bor —
`PaymentRequest.user` doim OLADIGAN odam, `requested_by` esa
to'lovni boshlagan odam.
"""

import logging

from core.models import ParentLink

from . import payment_requests, services
from .dates import format_money
from .services import BillingError

logger = logging.getLogger(__name__)


def can_view_reports(parent) -> bool:
    """
    Ota-ona farzandi hisobotini ko'ra oladimi.

    NARX NOLGA QO'YILGAN BO'LSA — HAMMAGA OCHIQ. Bu ataylab: yangi
    o'rnatilgan tizimda ota-onalarni birdaniga to'lovga tiqib
    qo'ymaslik kerak. Egasi panelda narx belgilagach darvoza yopiladi.
    """
    if not services.parent_reports_are_paid():
        return True
    return services.get_state(parent).active


def report_paywall_message() -> str:
    plan = services.get_parent_plan()
    return (
        f"Farzandingiz hisobotini ko'rish uchun obuna kerak: "
        f"{format_money(plan.price_per_month_tiyin)} / oy."
    )


def children_of(parent):
    """Ota-onaga biriktirilgan o'quvchilar."""
    return (
        ParentLink.objects.filter(parent=parent)
        .select_related('student__profile')
        .order_by('student__username')
    )


def create_child_request(parent, student_id: int, months: int):
    """
    Ota-ona FARZANDI uchun to'lov so'rovi ochadi.

    HUQUQ SHU YERDA TEKSHIRILADI: bog'lanish bo'lmasa so'rov ochilmaydi.
    Aks holda har kim istagan o'quvchi nomidan so'rov yaratib, uning
    to'lov oqimini chalkashtira olardi.

    So'rov O'QUVCHI nomiga ochiladi — pul uning obunasiga tushadi va
    tushum hisobotida o'quvchi tarifi bo'yicha ko'rinadi.
    """
    link = ParentLink.objects.filter(parent=parent, student_id=student_id).first()
    if link is None:
        raise BillingError(
            "Bu o'quvchi sizga biriktirilmagan.", status=403
        )

    created = payment_requests.create_request(link.student, months)
    created.requested_by = parent
    created.save(update_fields=['requested_by'])

    logger.info(
        "[OBUNA] Ota-ona %s farzandi %s uchun so'rov ochdi (#%s)",
        parent.username, link.student.username, created.pk,
    )
    return created
