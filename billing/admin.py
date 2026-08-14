"""
Obuna admin paneli
==================

Admin bu yerdan: tarifni sozlaydi, karta rekvizitlarini kiritadi, to'lov
so'rovlarini ko'rib chiqadi (karta berish / tasdiqlash / rad etish) va
bepul kun beradi.

MUHIM: davr jurnaliga (`SubscriptionPeriod`) admin panelidan QO'LDA
yozib bo'lmaydi. Yagona yo'l — `services.extend_subscription`, chunki u
`current_period_end` ni ham o'sha tranzaksiyada yangilaydi. Qo'lda yozish
ruxsat etilsa, jurnal bilan obuna sanasi bir-biriga to'g'ri kelmay
qolardi.
"""

import json

from django.contrib import admin, messages
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils.html import format_html

from . import dates, payment_requests
from .models import (
    AdminSetting,
    PaymentMethod,
    PaymentRequest,
    PeriodSource,
    RequestStatus,
    Subscription,
    SubscriptionPeriod,
    SubscriptionPlan,
)
from .services import (
    CARDS_KEY,
    STATUS_LABELS,
    BillingError,
    extend_subscription,
    get_state,
    grant_trial,
)


# ==========================================================================
# Tarif
# ==========================================================================


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'price_display', 'trial_days', 'grace_days', 'pending_hold_days', 'is_active')
    readonly_fields = ('created_at', 'updated_at', 'price_display', 'months_table')
    fieldsets = (
        ("Asosiy", {'fields': ('code', 'name', 'is_active')}),
        ("Narx", {
            'fields': ('price_per_month_tiyin', 'price_display', 'months_table'),
            'description': (
                "Narx <b>TIYINDA</b> kiritiladi: 99 000 so'm = <code>9900000</code>. "
                "Kasrli son ishlatilmaydi — pul hisobida u xatoga olib keladi."
            ),
        }),
        ("Muddatlar", {
            'fields': ('trial_days', 'grace_days', 'pending_hold_days'),
            'description': (
                "<b>Sinov kunlari</b> — 0 bo'lsa avtomatik berilmaydi, admin qo'lda beradi.<br>"
                "<b>Muhlat kunlari</b> — muddat tugagandan keyin qancha vaqt ishlashda davom etadi.<br>"
                "<b>Kutish kunlari</b> — o'quvchi \"chekni yubordim\" bosgandan keyin qancha vaqt "
                "qulflanmaydi. Tasdiqlash qo'lda bo'lgani uchun kerak."
            ),
        }),
        ("Vaqt", {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description="Oylik narx")
    def price_display(self, obj):
        return dates.format_money(obj.price_per_month_tiyin)

    @admin.display(description="Muddatlar bo'yicha narx")
    def months_table(self, obj):
        rows = "".join(
            f"<tr><td style='padding:2px 12px 2px 0'>{m} oy</td>"
            f"<td><b>{dates.format_money(obj.price_for(m))}</b></td></tr>"
            for m in dates.ALLOWED_MONTHS
        )
        return format_html("<table>{}</table>", format_html(rows))

    def has_delete_permission(self, request, obj=None):
        # Tarif o'chirilsa unga bog'langan davrlar (moliyaviy jurnal) yo'qoladi
        return False


# ==========================================================================
# Karta rekvizitlari
# ==========================================================================


@admin.register(AdminSetting)
class AdminSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'short_value', 'updated_at', 'updated_by')
    readonly_fields = ('updated_at', 'updated_by', 'hint')
    fields = ('key', 'value', 'hint', 'updated_at', 'updated_by')

    @admin.display(description="Qiymat")
    def short_value(self, obj):
        return (obj.value[:80] + '...') if len(obj.value) > 80 else obj.value

    @admin.display(description="Yordam")
    def hint(self, obj):
        return format_html(
            "Karta rekvizitlari uchun kalit: <code>{}</code><br>"
            "Qiymat — JSON massiv, bir nechta karta bo'lishi mumkin:<br>"
            "<pre>[\n"
            '  {{"number": "8600 1234 5678 9012", "holder": "OZODBEK T.", '
            '"bank": "Uzcard", "note": "Asosiy"}}\n'
            "]</pre>"
            "Bu rekvizitlar sahifada TURMAYDI — faqat so'rovi "
            "\"Karta berildi\" holatidagi o'quvchi ko'radi.",
            CARDS_KEY,
        )

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        # JSON buzilgan bo'lsa admin darhol bilsin — keyin jimgina bo'sh
        # ro'yxat qaytib, sabab noma'lum bo'lib qolardi
        if obj.key == CARDS_KEY and obj.value.strip():
            try:
                parsed = json.loads(obj.value)
                if not isinstance(parsed, list):
                    raise ValueError("massiv emas")
            except (json.JSONDecodeError, ValueError) as exc:
                messages.error(
                    request,
                    f"Karta ro'yxati JSON massiv bo'lishi kerak ({exc}). "
                    "Saqlandi, lekin o'quvchiga ko'rinmaydi.",
                )
        super().save_model(request, obj, form, change)


# ==========================================================================
# To'lov so'rovlari — asosiy ish joyi
# ==========================================================================


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user_link', 'months', 'amount_display', 'status_badge',
        'requested_at', 'receipt_sent_at', 'reviewed_by_admin',
    )
    list_filter = ('status', 'months', 'receipt_source')
    search_fields = ('user__username', 'user__email', 'user__profile__full_name')
    date_hierarchy = 'requested_at'
    actions = ['action_issue_card', 'action_confirm', 'action_expire']

    readonly_fields = (
        'user', 'plan', 'months', 'amount_display', 'status', 'requested_at',
        'expires_at', 'card_issued_at', 'receipt_sent_at', 'receipt_source',
        'confirmed_at', 'rejected_at', 'reviewed_by_admin', 'external_tx_id',
        'created_at', 'updated_at', 'flow_help',
    )
    fields = (
        'flow_help', 'user', 'plan', 'months', 'amount_display', 'status',
        'requested_at', 'expires_at', 'card_issued_at',
        'receipt_sent_at', 'receipt_source',
        'confirmed_at', 'rejected_at', 'reviewed_by_admin', 'admin_note',
    )

    @admin.display(description="Oqim")
    def flow_help(self, obj):
        return format_html(
            "<b>Yuborildi</b> → <b>Karta berildi</b> → <b>Chek yuborildi</b> → "
            "<b>Tasdiqlandi</b><br><br>"
            "Amallarni ro'yxat sahifasidagi <i>Action</i> menyusidan bajaring. "
            "Rad etish uchun <b>Admin izohi</b> ga sabab yozib saqlang, "
            "keyin \"Rad etish\" amalini tanlang.<br><br>"
            "<b>Diqqat:</b> tasdiqlash obunani uzaytiradi va jurnalga yozadi. "
            "Ikki marta bosilsa ikkinchisi bazada rad etiladi — obuna ikki "
            "marta uzaymaydi."
        )

    @admin.display(description="O'quvchi", ordering='user__username')
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user_id])
        name = obj.user.profile.full_name if hasattr(obj.user, 'profile') else ''
        return format_html('<a href="{}">{}</a>{}', url, obj.user.username,
                           format_html(' <small>({})</small>', name) if name else '')

    @admin.display(description="Summa", ordering='amount_tiyin')
    def amount_display(self, obj):
        return dates.format_money(obj.amount_tiyin)

    @admin.display(description="Holat", ordering='status')
    def status_badge(self, obj):
        colors = {
            RequestStatus.REQUESTED: '#f59e0b',
            RequestStatus.CARD_ISSUED: '#3b82f6',
            RequestStatus.RECEIPT_UPLOADED: '#8b5cf6',
            RequestStatus.CONFIRMED: '#10b981',
            RequestStatus.REJECTED: '#ef4444',
            RequestStatus.EXPIRED: '#6b7280',
        }
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:700">{}</span>',
            colors.get(obj.status, '#6b7280'), obj.get_status_display(),
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user__profile', 'plan', 'reviewed_by_admin')

    def has_add_permission(self, request):
        # So'rovni o'quvchining o'zi yaratadi
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def _run(self, request, queryset, func, ok_message):
        done, failed = 0, 0
        for obj in queryset:
            try:
                func(obj)
                done += 1
            except BillingError as exc:
                failed += 1
                messages.error(request, f"#{obj.pk}: {exc.message}")
        if done:
            messages.success(request, ok_message.format(count=done))
        if not done and not failed:
            messages.info(request, "Hech narsa o'zgarmadi.")

    @admin.action(description="1) Karta rekvizitlarini berish")
    def action_issue_card(self, request, queryset):
        self._run(
            request, queryset,
            lambda obj: payment_requests.issue_card(obj.pk, request.user),
            "{count} ta so'rovga karta berildi.",
        )

    @admin.action(description="2) Tasdiqlash — obunani uzaytiradi")
    def action_confirm(self, request, queryset):
        self._run(
            request, queryset,
            lambda obj: payment_requests.confirm_request(
                obj.pk, request.user, payment_method=PaymentMethod.CARD_TRANSFER
            ),
            "{count} ta to'lov tasdiqlandi va obuna uzaytirildi.",
        )

    @admin.action(description="Rad etish (Admin izohi to'ldirilgan bo'lishi kerak)")
    def action_expire(self, request, queryset):
        self._run(
            request, queryset,
            lambda obj: payment_requests.reject_request(obj.pk, request.user, obj.admin_note),
            "{count} ta so'rov rad etildi.",
        )


# ==========================================================================
# Obunalar
# ==========================================================================


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user_link', 'status_badge', 'end_display', 'days_left_display',
        'paid_total_display', 'periods_count',
    )
    list_filter = ('plan',)
    search_fields = ('user__username', 'user__email', 'user__profile__full_name')
    actions = ['action_grant_7_days', 'action_grant_30_days', 'action_grant_trial']

    readonly_fields = (
        'user', 'plan', 'current_period_end', 'hold_used_at',
        'last_reminder_days_left', 'created_at', 'updated_at',
        'status_badge', 'days_left_display', 'paid_total_display', 'grant_help',
    )
    fields = (
        'grant_help', 'user', 'plan', 'status_badge', 'current_period_end',
        'days_left_display', 'paid_total_display', 'hold_used_at',
        'last_reminder_days_left', 'created_at', 'updated_at',
    )

    @admin.display(description="Bepul kun berish")
    def grant_help(self, obj):
        return format_html(
            "Bepul kun berish uchun ro'yxat sahifasidagi <i>Action</i> menyusidan "
            "foydalaning. Bunday davr <b>ADMIN_GRANT</b> sifatida yoziladi va "
            "<b>tushum hisobotiga kirmaydi</b>.<br><br>"
            "Tugash sanasi shu yerdan qo'lda o'zgartirilmaydi — har o'zgarish "
            "jurnalga yozilishi kerak."
        )

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('user__profile', 'plan')
            .annotate(
                _periods=Count('periods', distinct=True),
                _paid=Sum('periods__amount_tiyin'),
            )
        )

    @admin.display(description="O'quvchi", ordering='user__username')
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)

    @admin.display(description="Holat")
    def status_badge(self, obj):
        state = get_state(obj.user)
        colors = {
            'ACTIVE': '#10b981', 'TRIAL': '#3b82f6', 'GRACE': '#f59e0b',
            'HOLD': '#8b5cf6', 'EXPIRED': '#ef4444', 'NONE': '#6b7280',
        }
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:700">{}</span>',
            colors.get(state.status, '#6b7280'),
            STATUS_LABELS.get(state.status, state.status),
        )

    @admin.display(description="Tugash sanasi", ordering='current_period_end')
    def end_display(self, obj):
        return dates.format_date(obj.current_period_end)

    @admin.display(description="Qolgan kun")
    def days_left_display(self, obj):
        if not obj.current_period_end:
            return "—"
        left = dates.days_left(obj.current_period_end)
        color = '#10b981' if left > 7 else ('#f59e0b' if left >= 0 else '#ef4444')
        return format_html('<b style="color:{}">{}</b>', color, left)

    @admin.display(description="Jami to'langan")
    def paid_total_display(self, obj):
        return dates.format_money(getattr(obj, '_paid', None) or 0)

    @admin.display(description="Davrlar")
    def periods_count(self, obj):
        return getattr(obj, '_periods', 0)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def _grant_days(self, request, queryset, days):
        done = 0
        for sub in queryset:
            try:
                extend_subscription(
                    sub.user, days=days, source=PeriodSource.ADMIN_GRANT,
                    note=f"Admin {days} kun bepul berdi", admin=request.user,
                )
                done += 1
            except BillingError as exc:
                messages.error(request, f"{sub.user.username}: {exc.message}")
        if done:
            messages.success(request, f"{done} ta o'quvchiga {days} kun bepul berildi.")

    @admin.action(description="Bepul 7 kun berish (ADMIN_GRANT)")
    def action_grant_7_days(self, request, queryset):
        self._grant_days(request, queryset, 7)

    @admin.action(description="Bepul 30 kun berish (ADMIN_GRANT)")
    def action_grant_30_days(self, request, queryset):
        self._grant_days(request, queryset, 30)

    @admin.action(description="Sinov muddatini berish (bir marta, TRIAL)")
    def action_grant_trial(self, request, queryset):
        done = 0
        for sub in queryset:
            try:
                grant_trial(sub.user, admin=request.user)
                done += 1
            except BillingError as exc:
                messages.error(request, f"{sub.user.username}: {exc.message}")
        if done:
            messages.success(request, f"{done} ta o'quvchiga sinov muddati berildi.")


# ==========================================================================
# Davr jurnali — faqat o'qish
# ==========================================================================


@admin.register(SubscriptionPeriod)
class SubscriptionPeriodAdmin(admin.ModelAdmin):
    """
    Moliyaviy jurnal. Qo'shish, o'zgartirish va o'chirish YOPIQ —
    yozuvlar faqat `services.extend_subscription` orqali paydo bo'ladi.
    """

    list_display = (
        'created_at', 'user_display', 'source_badge', 'payment_method',
        'months', 'amount_display', 'start_display', 'end_display', 'created_by_admin',
    )
    list_filter = ('source', 'payment_method', 'months')
    search_fields = ('subscription__user__username', 'subscription__user__email', 'note')
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'subscription__user', 'plan', 'created_by_admin', 'payment_request'
        )

    @admin.display(description="O'quvchi", ordering='subscription__user__username')
    def user_display(self, obj):
        return obj.subscription.user.username

    @admin.display(description="Manba", ordering='source')
    def source_badge(self, obj):
        colors = {
            PeriodSource.PAYMENT: '#10b981',
            PeriodSource.TRIAL: '#3b82f6',
            PeriodSource.ADMIN_GRANT: '#f59e0b',
            PeriodSource.MIGRATION: '#6b7280',
        }
        label = obj.get_source_display()
        if not obj.is_revenue:
            label += " (tushum emas)"
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:700">{}</span>',
            colors.get(obj.source, '#6b7280'), label,
        )

    @admin.display(description="Summa", ordering='amount_tiyin')
    def amount_display(self, obj):
        return dates.format_money(obj.amount_tiyin)

    @admin.display(description="Boshlanish", ordering='start_date')
    def start_display(self, obj):
        return dates.format_date(obj.start_date)

    @admin.display(description="Tugash", ordering='end_date')
    def end_display(self, obj):
        return dates.format_date(obj.end_date)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
