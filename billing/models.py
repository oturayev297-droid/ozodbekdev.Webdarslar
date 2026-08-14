"""
Obuna va to'lov modellari
=========================

DIZAYN QOIDALARI (buzilmasligi kerak):

1. Narxlar TIYINDA, butun son. Kasrli son ishlatilmaydi.
2. Obuna holati BAYROQDAN emas, `Subscription.current_period_end` dan
   HISOBLANADI. Bayroq bo'lsa u sana bilan bir-biriga to'g'ri kelmay
   qolishi muqarrar.
3. `SubscriptionPeriod` — moliyaviy JURNAL. Yozilgandan keyin
   o'zgartirilmaydi (`updated_at` ataylab yo'q) va o'chirilmaydi.
4. Har uzaytirish `SubscriptionPeriod` yozuvi bilan BIRGA, bitta
   tranzaksiyada bo'ladi. `current_period_end` ni o'zgartiradigan yagona
   joy — `services.extend_subscription`.
5. Narx davrga KO'CHIRILADI (`amount_tiyin`, `plan`). Hisobot joriy
   narxga bog'lanmaydi — aks holda narx oshirilganda o'tgan tushum
   tarixi qayta hisoblanib, hisobot yolg'on chiqardi.
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from .dates import ALLOWED_MONTHS, format_money


class SubscriptionPlan(models.Model):
    """Tarif. Hozircha bitta faol tarif bor, lekin model bir nechtasini ko'taradi."""

    #: Ichki kalit: "STUDENT_MONTHLY"
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)

    #: Bir oylik narx — TIYINDA, butun son.
    #: PositiveIntegerField chegarasi ~21.4 mln so'm — 12 oylik to'lov ham sig'adi.
    price_per_month_tiyin = models.PositiveIntegerField(
        help_text="Bir oylik narx TIYINDA (100 000 so'm = 10000000)"
    )

    #: Sinov kunlari. 0 = avtomatik trial berilmaydi, admin qo'lda beradi.
    trial_days = models.PositiveIntegerField(
        default=0,
        help_text="Avtomatik sinov kunlari. 0 = faqat admin qo'lda beradi.",
    )

    #: Tugagandan keyin necha kun ishlashda davom etadi.
    #: Bazada, chunki deploy kutmasdan o'zgarishi kerak.
    grace_days = models.PositiveIntegerField(
        default=3, help_text="Muddat tugagandan keyin qo'shimcha ishlash kunlari"
    )

    #: "Chekni yubordim" bosilgandan keyin qulflash necha kun to'xtab turadi.
    #:
    #: NEGA KERAK: muhlat 3 kun, tasdiqlash esa qo'lda. O'quvchi 2-kuni
    #: to'lasa, admin 4-kuni ko'rsa — o'quvchi pulni to'lab turib NOTO'G'RI
    #: qulflanardi. Kutish rejimi shu bo'shliqni yopadi.
    pending_hold_days = models.PositiveIntegerField(
        default=5, help_text="Chek yuborilgandan keyin kutish kunlari"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tarif"
        verbose_name_plural = "Tariflar"

    def __str__(self):
        return f"{self.name} — {format_money(self.price_per_month_tiyin)}/oy"

    def price_for(self, months: int) -> int:
        """Berilgan oy soni uchun summa (tiyinda). Faqat serverda hisoblanadi."""
        return self.price_per_month_tiyin * months


class Subscription(models.Model):
    """
    O'quvchining obuna holati.

    Har foydalanuvchiga avtomatik yaratilmaydi — faqat kerak bo'lganda
    (`services.ensure_subscription`). Shuning uchun obunasi yo'q oddiy
    foydalanuvchini o'chirib bo'ladi.
    """

    #: PROTECT: obunasi (demak to'lov tarixi) bor o'quvchini o'chirib
    #: bo'lmaydi. Uni faolsizlantirish kerak — moliyaviy yozuv yo'qolmasin.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='subscription',
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')

    #: Amaldagi tugash vaqti. UTC da saqlanadi, lekin Asia/Tashkent
    #: bo'yicha kun oxiriga yaxlitlanadi.
    #:
    #: BOOLEAN BAYROQ YO'Q: holat shu sanadan HISOBLANADI.
    current_period_end = models.DateTimeField(null=True, blank=True, db_index=True)

    #: ─── KUTISH REJIMI ───
    #: O'quvchi "Chekni yubordim" bosgan payt. Shu payt +
    #: plan.pending_hold_days gacha kirish ochiq qoladi, muhlat tugagan
    #: bo'lsa ham.
    #:
    #: BIR DAVRDA BIR MARTA: yangi davr yaratilganda `None` ga
    #: qaytariladi (o'sha tranzaksiyada). Shuning uchun o'quvchi
    #: qayta-qayta "to'ladim" deb cheksiz uzaytira olmaydi.
    #:
    #: Kutish AMALDA ekani yana bitta shartga bog'liq: unda hali
    #: RECEIPT_UPLOADED holatidagi so'rov turgan bo'lishi. Admin rad etsa
    #: holat o'zgaradi va kutish DARHOL tugaydi.
    hold_used_at = models.DateTimeField(null=True, blank=True)

    #: Oxirgi yuborilgan eslatma qaysi chegara uchun edi (7, 3 yoki 0).
    #: Busiz kunlik tekshiruv har yurishda o'sha xabarni qayta yuborardi.
    #: Obuna uzaytirilganda `None` ga qaytariladi.
    last_reminder_days_left = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Obuna"
        verbose_name_plural = "Obunalar"

    def __str__(self):
        return f"{self.user.username} — {self.current_period_end or 'muddat yo\'q'}"


class PeriodSource(models.TextChoices):
    """
    Davr qayerdan kelgani.

    TUSHUM HISOBOTI FAQAT `PAYMENT` dan yig'iladi. `ADMIN_GRANT` — bepul
    berilgan davr, u tushum EMAS va hisobotga qo'shilmaydi. Bu farq
    yo'qolsa, oylik tushum yolg'on chiqadi.
    """

    TRIAL = 'TRIAL', "Sinov muddati"
    PAYMENT = 'PAYMENT', "To'lov"
    ADMIN_GRANT = 'ADMIN_GRANT', "Admin bepul berdi"
    MIGRATION = 'MIGRATION', "Tizim joriy qilinganda"


class PaymentMethod(models.TextChoices):
    """
    To'lov qanday kelgani.

    DIQQAT: bu `PeriodSource` ning O'RNINI BOSMAYDI.
      * source = pul kelganmi yoki bepul berilganmi
      * method = pul QANDAY kelgani
    Naqd to'lov ham to'lov: source=PAYMENT, method=CASH — tushumga
    kiradi. Bepul berish: source=ADMIN_GRANT, method=None.
    """

    CASH = 'CASH', "Naqd"
    CARD_TRANSFER = 'CARD_TRANSFER', "Kartaga o'tkazma"
    CLICK = 'CLICK', "Click"
    PAYME = 'PAYME', "Payme"


class RequestStatus(models.TextChoices):
    """To'lov so'rovining holati.

    REQUESTED -> CARD_ISSUED -> RECEIPT_UPLOADED -> CONFIRMED
    """

    REQUESTED = 'REQUESTED', "Yuborildi"
    CARD_ISSUED = 'CARD_ISSUED', "Karta berildi"
    RECEIPT_UPLOADED = 'RECEIPT_UPLOADED', "Chek yuborildi"
    CONFIRMED = 'CONFIRMED', "Tasdiqlandi"
    REJECTED = 'REJECTED', "Rad etildi"
    EXPIRED = 'EXPIRED', "Javobsiz qoldi"


class ReceiptSource(models.TextChoices):
    """Chek qaysi yo'l bilan yuborilgani.

    Fayl ILOVAGA YUKLANMAYDI — bu faqat adminga signal, chek Telegramda
    yoki boshqa kanalda ko'riladi.
    """

    TELEGRAM = 'TELEGRAM', "Telegram"
    EMAIL = 'EMAIL', "Email"
    OTHER = 'OTHER', "Boshqa"


#: "Ochiq" hisoblanadigan holatlar — bazadagi qisman unique indeks bilan bir xil
OPEN_STATUSES = (
    RequestStatus.REQUESTED,
    RequestStatus.CARD_ISSUED,
    RequestStatus.RECEIPT_UPLOADED,
)


class PaymentRequest(models.Model):
    """
    To'lov so'rovi.

    Karta rekvizitlari sahifada TURMAYDI: o'quvchi so'rov yuboradi, admin
    bergandan keyingina ko'radi. Shu sabab bu jadval kerak.
    """

    #: PROTECT: to'lov so'rovi bor o'quvchini o'chirib bo'lmaydi
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='payment_requests'
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='payment_requests')

    #: 1, 3, 6 yoki 12. Baza darajasida ham cheklangan.
    months = models.PositiveIntegerField()

    #: Summa HAR DOIM serverda plandan hisoblanadi. Klientdan kelgan
    #: qiymat butunlay e'tiborsiz qoldiriladi.
    amount_tiyin = models.PositiveIntegerField()

    status = models.CharField(
        max_length=20, choices=RequestStatus.choices, default=RequestStatus.REQUESTED, db_index=True
    )

    requested_at = models.DateTimeField(auto_now_add=True)

    #: Javobsiz qolsa shu vaqtdan keyin EXPIRED bo'ladi.
    #:
    #: MUHIM: avtomatik kuyish FAQAT REQUESTED va CARD_ISSUED holatlariga
    #: tegishli. RECEIPT_UPLOADED hech qachon o'z-o'zidan kuymaydi —
    #: o'quvchi pulni yuborib, tasdiq kutib turganda so'rovi yo'qolsa,
    #: pul ketgan bo'lardi. Uni faqat admin yopadi.
    expires_at = models.DateTimeField()

    card_issued_at = models.DateTimeField(null=True, blank=True)

    #: O'quvchi "Chekni yubordim" tugmasini bosgan vaqt. Fayl so'ralmaydi.
    receipt_sent_at = models.DateTimeField(null=True, blank=True)
    receipt_source = models.CharField(
        max_length=20, choices=ReceiptSource.choices, null=True, blank=True
    )

    confirmed_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)

    #: Kartani bergan / tasdiqlagan / rad etgan admin
    reviewed_by_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_payment_requests',
    )

    #: Rad etish sababi ham shu yerda
    admin_note = models.TextField(blank=True)

    #: KELAJAK UCHUN: Click/Payme tranzaksiya id si. Hozir ishlatilmaydi,
    #: lekin unique bo'lgani uchun takror webhook ikkinchi yozuv yarata
    #: olmaydi — idempotentlik naqshi bir xil qoladi.
    external_tx_id = models.CharField(max_length=100, unique=True, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "To'lov so'rovi"
        verbose_name_plural = "To'lov so'rovlari"
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user', '-requested_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(months__in=ALLOWED_MONTHS),
                name='payment_request_months_allowed',
            ),
            # BITTA OCHIQ SO'ROV: ikkita so'rov bir vaqtda kelsa ham
            # bazaning o'zi ikkinchisini rad etadi. Ilova darajasidagi
            # tekshiruv poygaga tushardi.
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(status__in=[s.value for s in OPEN_STATUSES]),
                name='one_open_payment_request_per_user',
            ),
        ]

    def __str__(self):
        return f"#{self.pk} {self.user.username} — {self.months} oy ({self.get_status_display()})"


class SubscriptionPeriod(models.Model):
    """
    Davr jurnali — o'chirilmaydi, tahrirlanmaydi.

    `updated_at` ATAYLAB YO'Q: bu jurnal, yozilgandan keyin o'zgarmaydi.
    """

    #: PROTECT: moliyaviy jurnal obuna o'chirilsa ham qolishi kerak
    subscription = models.ForeignKey(
        Subscription, on_delete=models.PROTECT, related_name='periods'
    )

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    #: To'lov davrlari uchun necha oy. TRIAL/ADMIN_GRANT uchun None.
    months = models.PositiveIntegerField(null=True, blank=True)

    source = models.CharField(max_length=20, choices=PeriodSource.choices, db_index=True)

    #: To'lov qanday kelgani. PAYMENT uchun MAJBURIY, boshqalari uchun None.
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, null=True, blank=True
    )

    #: IDEMPOTENTLIK KALITI. Bitta to'lov so'rovi ko'pi bilan BITTA davr
    #: yaratadi — bazaning o'zi kafolatlaydi. Tasdiqlash tugmasi ikki
    #: marta bosilsa ham (yoki kelajakda webhook takror kelsa ham) obuna
    #: IKKI MARTA UZAYMAYDI.
    #:
    #: NAQD TO'LOVDA None bo'ladi: so'rov umuman yaratilmaydi, admin
    #: to'g'ridan-to'g'ri davr yozadi. Unique indeksda bir nechta NULL
    #: bir-biriga TENG EMAS, shuning uchun bir necha naqd yozuv bemalol
    #: yonma-yon turadi.
    payment_request = models.OneToOneField(
        PaymentRequest,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='period',
    )

    #: ─── NARX MUZLATILADI ───
    #: To'lov paytidagi summa VA tarif shu yerga KO'CHIRILADI. Hisobot
    #: FAQAT shu maydonlardan o'qiydi va SubscriptionPlan ga bog'lanib
    #: joriy narxni OLMAYDI.
    amount_tiyin = models.PositiveIntegerField(null=True, blank=True)
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, null=True, blank=True, related_name='periods'
    )

    #: SET_NULL: admin hisobi ketsa ham davr qoladi, faqat kim bergani noma'lum bo'ladi
    created_by_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_periods',
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    # updated_at ATAYLAB YO'Q — bu jurnal

    class Meta:
        verbose_name = "Obuna davri"
        verbose_name_plural = "Obuna davrlari (jurnal)"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', '-end_date']),
        ]
        constraints = [
            # source va payment_method bog'liqligi baza darajasida
            models.CheckConstraint(
                check=(
                    models.Q(source=PeriodSource.PAYMENT, payment_method__isnull=False)
                    | (~models.Q(source=PeriodSource.PAYMENT) & models.Q(payment_method__isnull=True))
                ),
                name='payment_method_only_for_payment_source',
            ),
            models.CheckConstraint(
                check=models.Q(end_date__gt=models.F('start_date')),
                name='period_end_after_start',
            ),
        ]

    def __str__(self):
        return f"{self.subscription.user.username}: {self.get_source_display()} -> {self.end_date:%d.%m.%Y}"

    @property
    def is_revenue(self) -> bool:
        """Tushum hisobotiga kiradimi."""
        return self.source == PeriodSource.PAYMENT


class AdminSetting(models.Model):
    """
    Admin sozlamalari (kalit-qiymat).

    Karta rekvizitlari SHU YERDA saqlanadi — kodda ham, shablonda ham
    emas. Admin deploy qilmasdan o'zgartira oladi.

    KIRISH QAT'IY CHEKLANGAN: kartaga yagona boshqa yo'l — o'quvchining
    O'ZIDA CARD_ISSUED holatidagi so'rov bo'lishi. Boshqa yo'l
    qoldirilmaydi.
    """

    key = models.CharField(max_length=100, primary_key=True)
    value = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name = "Admin sozlamasi"
        verbose_name_plural = "Admin sozlamalari"

    def __str__(self):
        return self.key
