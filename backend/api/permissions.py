"""
API huquqlari
=============

ENG MUHIM QOIDA: API DARVOZANI QAYTA YOZMAYDI.

Shablonli sahifalar `core.approval` va `billing.gating` orqali
himoyalangan. API o'sha AYNAN SHU funksiyalarni chaqiradi. Agar bu
yerda mustaqil `if` yozilsa, ikki joyda ikki xil qoida paydo bo'lardi
va biri o'zgarganda ikkinchisi ochiq qolib ketardi — ya'ni API
paywallda teshik bo'lardi.

UCH QATLAM (har biri o'zidan oldingisiga qo'shiladi):

    IsAuthenticated  -> tizimga kirgan
    IsApproved       -> admin ruxsat bergan
    HasSubscription  -> joriy oy uchun to'lov qilingan

Dars darajasidagi cheklov uchun `billing.gating.can_access_lesson`
ishlatiladi — u bepul darslarni o'tkazadi.
"""

from rest_framework import permissions

from billing.services import get_state
from core.approval import is_approved


class IsApproved(permissions.BasePermission):
    """
    Admin ruxsati bo'lgan foydalanuvchi.

    Xodim har doim o'tadi — `core.approval.is_approved` da shunday
    hal qilingan va bu yerda takrorlanmaydi.
    """

    message = (
        "Hisobingiz hali tasdiqlanmagan. Administrator ruxsat bergach "
        "darslar ochiladi."
    )
    code = 'APPROVAL_REQUIRED'

    def has_permission(self, request, view):
        return is_approved(request.user)


class HasSubscription(permissions.BasePermission):
    """
    Faol obunasi bor foydalanuvchi.

    DIQQAT: bu BUTUN bo'limni yopadi. Bepul darslar o'tishi kerak
    bo'lgan joyda ishlatilmaydi — u yerda `can_access_lesson`
    chaqiriladi.
    """

    message = "Bu bo'lim obuna talab qiladi."
    code = 'SUBSCRIPTION_REQUIRED'

    def has_permission(self, request, view):
        return get_state(request.user).active


class IsStaff(permissions.BasePermission):
    """Panel uchun. `panel.auth.staff_required` bilan bir xil shart."""

    message = "Bu bo'lim faqat xodimlar uchun."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class ReadOnly(permissions.BasePermission):
    """Faqat o'qish. Boshqa huquq bilan birga ishlatiladi."""

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS
