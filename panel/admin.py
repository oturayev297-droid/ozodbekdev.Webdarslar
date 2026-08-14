"""
Panel xabarlarining Django admin ko'rinishi.

FAQAT O'QISH UCHUN. Yuborish `/panel/xabarlar/` da bo'ladi — bu yerda
xabar yaratib bo'lmaydi, chunki Django admin formasi oluvchilar
ro'yxatini qurmaydi va yuborishni boshlamaydi. Yaratishga yo'l
qo'yilsa, hech qachon yuborilmaydigan "arvoh" xabarlar paydo bo'lardi.

Jurnal tahrirlanmaydi ham: "men bunday yozmagandim" degan bahsni faqat
o'zgarmas yozuv yopadi.
"""

from django.contrib import admin

from .models import PanelDelivery, PanelMessage


class DeliveryInline(admin.TabularInline):
    model = PanelDelivery
    extra = 0
    can_delete = False
    fields = ('user', 'chat_id', 'state', 'error', 'sent_at')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PanelMessage)
class PanelMessageAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'audience', 'sent_by', 'progress', 'status')
    list_filter = ('status', 'audience', 'created_at')
    search_fields = ('body', 'sent_by__username', 'target_user__username')
    date_hierarchy = 'created_at'
    inlines = [DeliveryInline]

    readonly_fields = (
        'sent_by', 'audience', 'target_user', 'body', 'status',
        'total', 'delivered', 'failed', 'created_at', 'finished_at',
    )

    @admin.display(description="Yetkazildi")
    def progress(self, obj):
        text = f"{obj.delivered}/{obj.total}"
        if obj.failed:
            text += f" (xato: {obj.failed})"
        return text

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
