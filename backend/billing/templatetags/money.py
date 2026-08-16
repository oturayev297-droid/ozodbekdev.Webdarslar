"""Pulni ko'rsatish uchun shablon filtrlari.

Narxlar bazada TIYINDA saqlanadi, ekranda so'mda ko'rsatiladi.
Aylantirish faqat shu yerda — shablonda `tiyin / 100` yozilmaydi.
"""

from django import template

from billing import dates

register = template.Library()


@register.filter(name='money')
def money(tiyin):
    """9900000 -> "99 000 so'm" """
    return dates.format_money(tiyin)


@register.filter(name='soum')
def soum(tiyin):
    """9900000 -> "99 000" (birliksiz)"""
    return f"{dates.tiyin_to_soum(tiyin):,}".replace(",", " ")


@register.filter(name='tashkent_date')
def tashkent_date(value):
    """Sanani Toshkent kuni bo'yicha "02.08.2026" ko'rinishida beradi."""
    return dates.format_date(value)
