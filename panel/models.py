"""
Panel modellari
===============

Bu yerda FAQAT panelning o'ziga tegishli narsalar bor: yuborilgan
xabarlar jurnali. Dars, obuna, to'lov modellari `core` va `billing` da
qoladi — panel ularni faqat KO'RSATADI va mavjud xizmat funksiyalari
orqali o'zgartiradi.

NEGA XABAR IKKI JADVALGA BO'LINGAN:

  * `PanelMessage`  — bitta yuborish hodisasi (matn, kim yubordi, kimga)
  * `PanelDelivery` — har bir oluvchi uchun alohida qator

Bitta jadval bo'lganda 300 kishilik xabar yuborish yarmida uzilib qolsa,
qayta urinishda kim olganini bilib bo'lmasdi — hamma qaytadan olardi.
Har oluvchi alohida qator bo'lgani uchun yuborish TO'XTAGAN JOYIDAN
davom etadi.
"""

from django.conf import settings
from django.db import models


class Audience(models.TextChoices):
    """Xabar kimga ketadi."""

    ONE = 'ONE', "Bitta o'quvchi"
    ALL = 'ALL', "Hamma (Telegrami ulanganlar)"
    ACTIVE = 'ACTIVE', "Obunasi faollar"
    EXPIRING = 'EXPIRING', "Muddati 7 kunda tugaydiganlar"
    EXPIRED = 'EXPIRED', "Obunasi tugaganlar"


class MessageStatus(models.TextChoices):
    PENDING = 'PENDING', "Navbatda"
    DONE = 'DONE', "Yuborildi"
    FAILED = 'FAILED', "Yetkazilmadi"


class PanelMessage(models.Model):
    """
    Yuborilgan xabar.

    JURNAL: o'chirilmaydi va matni tahrirlanmaydi. "Men bunday
    yozmagandim" degan bahsni faqat o'zgarmas yozuv yopadi.
    """

    #: SET_NULL: xodim hisobi ketsa ham xabar tarixi qoladi
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='panel_messages',
    )

    audience = models.CharField(max_length=20, choices=Audience.choices)

    #: audience=ONE bo'lganda — qaysi o'quvchi
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='panel_messages_received',
    )

    body = models.TextField()

    status = models.CharField(
        max_length=20, choices=MessageStatus.choices, default=MessageStatus.PENDING, db_index=True
    )

    #: Yaratilganda hisoblanadi va o'zgarmaydi — keyin auditoriya
    #: o'zgarsa ham "o'shanda nechta odamga ketgani" saqlanib qoladi.
    total = models.PositiveIntegerField(default=0)
    delivered = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Panel xabari"
        verbose_name_plural = "Panel xabarlari"
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.pk} {self.get_audience_display()} — {self.delivered}/{self.total}"

    @property
    def pending_count(self) -> int:
        return self.total - self.delivered - self.failed


class PanelDelivery(models.Model):
    """Bitta oluvchiga yuborish urinishi."""

    class State(models.TextChoices):
        PENDING = 'PENDING', "Navbatda"
        SENT = 'SENT', "Yuborildi"
        FAILED = 'FAILED', "Xato"

    message = models.ForeignKey(PanelMessage, on_delete=models.CASCADE, related_name='deliveries')

    #: CASCADE: o'quvchi o'chirilsa yetkazish qatori ham ketadi.
    #: Umumiy hisob `PanelMessage.total` da MUZLATIB qo'yilgani uchun
    #: hisobot buzilmaydi.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='panel_deliveries'
    )

    #: Yuborish paytidagi chat id. Keyin o'quvchi Telegramni uzsa ham
    #: xabar QAYERGA ketgani ma'lum bo'lib qoladi.
    chat_id = models.CharField(max_length=64, blank=True)

    state = models.CharField(
        max_length=20, choices=State.choices, default=State.PENDING, db_index=True
    )
    error = models.CharField(max_length=200, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Xabar yetkazish"
        verbose_name_plural = "Xabar yetkazishlar"
        constraints = [
            # Bitta xabar bitta odamga BIR MARTA ketadi. Yuborish uzilib
            # qayta ishga tushsa ham takror kelmaydi.
            models.UniqueConstraint(
                fields=['message', 'user'], name='one_delivery_per_user_per_message'
            ),
        ]
        indexes = [
            models.Index(fields=['message', 'state']),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.get_state_display()}"
