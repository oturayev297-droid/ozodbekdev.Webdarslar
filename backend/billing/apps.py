from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "billing"

    def ready(self):
        # Sozlama tekshiruvlari `manage.py check` da ishlashi uchun
        # ro'yxatdan o'tishi kerak. Import qilishning o'zi yetarli —
        # `@register()` shu paytda bajariladi.
        from . import checks  # noqa: F401
