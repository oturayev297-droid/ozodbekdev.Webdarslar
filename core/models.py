from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"

class Module(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.category.name} - {self.title}"

    class Meta:
        ordering = ['order']

class Lesson(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    #: Dars matni. ODDIY MATN sifatida yoziladi va serverda
    #: `core.richtext.render` orqali HTML ga aylantiriladi. Bu yerga
    #: tayyor HTML yozish KERAK EMAS — u ekranlanadi va matn bo'lib
    #: ko'rinadi. Qo'llab-quvvatlanadigan belgilar ro'yxati
    #: `core/richtext.py` da.
    theory = models.TextField(
        default="",
        verbose_name="Dars matni",
        help_text=(
            "Oddiy matn. Bezaklar: ## sarlavha, **qalin**, `kod`, "
            "- ro'yxat, > eslatma, ``` kod bloki ```"
        ),
    )
    practice_code = models.TextField(blank=True, default="", help_text="Amaliy kod namunalari uchun")
    video_url = models.URLField(blank=True, null=True)
    video_file = models.FileField(upload_to='lesson_videos/', blank=True, null=True, help_text="Dars videosini yuklash")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    #: Bepul dars — tizimga kirgan har kimga ochiq. Qolganlari obuna
    #: talab qiladi.
    #:
    #: DEFAULT False (fail closed): yangi dars yopiq tug'iladi. Bayroqni
    #: qo'yishni unutish kontentni bepul qilib qo'ymaydi. Bepul qilish
    #: har doim ONGLI qaror bo'lishi kerak.
    is_free = models.BooleanField(
        default=False,
        verbose_name="Bepul dars",
        help_text="Belgilansa, obunasiz ham ochiq bo'ladi (tanishtiruv darsi)",
    )

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['order']


class LessonImage(models.Model):
    """
    Dars matnidagi rasm (sxema, ekran tasviri, misol).

    NEGA ALOHIDA MODEL, matn ichiga havola yozish emas:

    1. Fayl bazada boshqariladi. Matn ichiga qo'lda havola yozilsa,
       fayl o'chirilganda yoki nomi o'zgarganda "singan rasm"
       belgisi qolardi va buni hech kim sezmasdi.
    2. Rasm QULFLANGAN darsdan ham yashirilishi kerak. Alohida model
       bo'lgani uchun uni JSON ga qo'shmaslik bitta shart bilan hal
       bo'ladi — matn ichidagi havolani esa ajratib olish kerak edi.
    3. Bir darsga bir necha rasm, tartib va izoh bilan.

    Rasmlar `/media/lesson_images/` da va ular VIDEODAN FARQLI o'laroq
    ochiq beriladi: rasm — bu kontentning kichik qismi, uni himoyalash
    uchun har biriga alohida so'rov qilish arzimaydi. Video esa
    darsning O'ZI, shuning uchun u faqat `/lessons/<id>/video/` orqali.
    """

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='images')

    image = models.ImageField(upload_to='lesson_images/', verbose_name="Rasm")

    #: Rasm tagida chiqadi. Bo'sh bo'lsa izoh ko'rsatilmaydi.
    caption = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="Izoh",
        help_text="Rasm tagida chiqadigan matn",
    )

    #: Ko'rmaydiganlar uchun tavsif. Bo'sh bo'lsa `caption` ishlatiladi.
    alt_text = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Muqobil matn",
        help_text="Rasm ochilmasa yoki ekran o'qigich uchun tavsif",
    )

    order = models.PositiveIntegerField(default=0, verbose_name="Tartib")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Dars rasmi"
        verbose_name_plural = "Dars rasmlari"
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.lesson.title} — rasm #{self.order}"

    @property
    def display_alt(self) -> str:
        return self.alt_text or self.caption or self.lesson.title


class Quiz(models.Model):
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='quiz')
    title = models.CharField(max_length=200)
    time_limit = models.PositiveIntegerField(default=20, help_text="Testni topshirish vaqti (minutda)")

    #: Nashr qilinganmi. False bo'lsa o'quvchi umuman ko'rmaydi.
    #:
    #: DEFAULT True: admin panelda qo'lda yaratilgan test darhol ishlaydi —
    #: bu odatiy kutilgan xatti-harakat. `generate_quizzes` buyrug'i esa
    #: ATAYLAB False qo'yadi: model yozgan savol tekshirilmaguncha
    #: o'quvchiga ko'rinmasligi kerak. Noto'g'ri savol o'quvchini
    #: chalg'itadi va sertifikatni ma'nosiz qiladi.
    is_published = models.BooleanField(
        default=True,
        verbose_name="Nashr qilingan",
        help_text="Olib tashlansa o'quvchi bu testni ko'rmaydi (qoralama)",
    )

    #: Kim yozgani — qoralamalarni ajratish uchun
    is_generated = models.BooleanField(
        default=False,
        verbose_name="Model generatsiya qilgan",
        help_text="Avtomatik yozilgan. Nashrdan oldin tekshirilishi shart.",
    )

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Test"
        verbose_name_plural = "Testlar"

    def __str__(self):
        return self.title

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()

    def __str__(self):
        return self.text[:50]

class QuizResult(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='quiz_results')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='results')
    score_percentage = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    correct_count = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=1, help_text="Nechinchi urinish")
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']
        unique_together = ('user', 'quiz')

    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} ({self.score_percentage}%)"

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text

class Project(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    image_url = models.URLField(blank=True, null=True, help_text="Loyiha uchun mockup yoki rasm URL")
    difficulty = models.CharField(max_length=50, choices=[('Entry', 'Entry'), ('Pro', 'Pro'), ('Architect', 'Architect')], default='Entry')
    tech_stack = models.CharField(max_length=255, help_text="Texnologiyalar (vergul bilan ajrating: React, Node.js, JS)")
    demo_url = models.URLField(blank=True, null=True)
    repo_url = models.URLField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['order']

class Challenge(models.Model):
    DIFFICULTY_CHOICES = [
        ('Oson', 'Oson'),
        ('O\'rtacha', 'O\'rtacha'),
        ('Qiyin', 'Qiyin'),
    ]

    class Language(models.TextChoices):
        PYTHON = 'python', "Python"
        JAVASCRIPT = 'javascript', "JavaScript"

    #: Topshiriq qaysi tilda yechiladi.
    #:
    #: DEFAULT PYTHON: platforma asosan Python o'rgatadi va muharrirdagi
    #: fayl "practice.py" deb ataladi. Ilgari muharrir tildan qat'i nazar
    #: faqat JavaScript `eval()` qilardi — Python kodini yozib bo'lmasdi.
    language = models.CharField(
        max_length=20,
        choices=Language.choices,
        default=Language.PYTHON,
        verbose_name="Til",
    )

    title = models.CharField(max_length=200)
    description = models.TextField(help_text="Topshiriq matni (HTML/Markdown qo'llab-quvvatlaydi)")
    initial_code = models.TextField(default="// Kodni shu yerga yozing...", help_text="Muharrirdagi dastlabki kod")
    solution_code = models.TextField(blank=True, help_text="To'g'ri javob kodi (tekshirish uchun)")
    order = models.PositiveIntegerField(default=0)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='Oson')

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['order']

class Profile(models.Model):
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    level = models.PositiveIntegerField(default=1)

    #: Telegram chat ID. Bo'sh bo'lsa xabarnomalar faqat emailga ketadi.
    #: Bir martalik havola orqali ulanadi — telefon raqami so'ralmaydi.
    telegram_chat_id = models.CharField(
        max_length=32, blank=True, db_index=True,
        verbose_name="Telegram chat ID",
        help_text="Bir martalik havola orqali avtomatik to'ldiriladi",
    )

    #: ─── ADMIN RUXSATI ───
    #:
    #: Ro'yxatdan o'tishning O'ZI kirish huquqini bermaydi. Admin
    #: paneldan ruxsat bermaguncha o'quvchi darslarni ko'rmaydi.
    #:
    #: DEFAULT False (fail closed): yangi hisob YOPIQ tug'iladi.
    #: Teskarisi bo'lganda, ro'yxatdan o'tish formasini topgan har kim
    #: darhol ichkariga kirardi va bu e'tibordan chetda qolardi.
    #:
    #: BU OBUNANING O'RNINI BOSMAYDI. Ikkalasi ham kerak:
    #:   ruxsat  = adminning bu odamni tanishi
    #:   obuna   = joriy oy uchun to'lov qilinganligi
    #: Ruxsat bir marta beriladi, obuna esa har oy yangilanadi.
    is_approved = models.BooleanField(
        default=False,
        verbose_name="Ruxsat berilgan",
        help_text="Olib tashlansa o'quvchi darslarni ko'rmaydi",
    )

    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="Ruxsat vaqti")

    #: SET_NULL: admin hisobi ketsa ham ruxsat qolаdi
    approved_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_students',
        verbose_name="Kim ruxsat berdi",
    )

    #: Rad etilgan bo'lsa sababi. O'quvchiga KO'RSATILADI, shuning uchun
    #: ichki izoh emas — tushunarli qilib yoziladi.
    rejection_reason = models.TextField(blank=True, verbose_name="Rad etish sababi")

    def __str__(self):
        return self.user.username

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Yangi User yaratilganda unga Profile ochib beradi."""
    if created:
        Profile.objects.get_or_create(user=instance)

class UserProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='user_progress')
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'lesson')
        indexes = [
            models.Index(fields=['user', 'is_completed']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.lesson.title}"

class NewStudent(Profile):
    class Meta:
        proxy = True
        verbose_name = "Yangi O'quvchi (Buyurtma)"
        verbose_name_plural = "Yangi O'quvchilar (Buyurtmalar)"


class Certificate(models.Model):
    """
    Sertifikat.

    NEGA JADVAL KERAK: sertifikatni "80%+ ball olganlarga" deb har safar
    QuizResult dan hisoblash mumkin edi — lekin unda tashqi tekshirish
    imkoni bo'lmasdi va natija keyin o'zgarsa (masalan test qayta
    topshirilib ball tushsa) allaqachon berilgan sertifikat "yo'qolib"
    qolardi. Berilgan sertifikat — o'zgarmas fakt.

    NARX/BALL MUZLATILADI: `score_percentage` shu yerga KO'CHIRILADI va
    QuizResult ga bog'lanib o'qilmaydi.
    """

    #: Tashqi tekshirish uchun ochiq identifikator. Ketma-ket ID
    #: ISHLATILMAYDI: /verify/1, /verify/2 deb yurib boshqalarning
    #: sertifikatlarini sanab chiqib bo'lardi.
    code = models.CharField(max_length=32, unique=True, db_index=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificates')
    quiz = models.ForeignKey('Quiz', on_delete=models.PROTECT, related_name='certificates')

    #: Berilgan paytdagi qiymatlar — keyin o'zgarmaydi
    score_percentage = models.PositiveIntegerField()
    full_name = models.CharField(max_length=255, blank=True)
    quiz_title = models.CharField(max_length=200)
    category_name = models.CharField(max_length=100, blank=True)

    issued_at = models.DateTimeField(auto_now_add=True)

    #: Admin bekor qilishi mumkin (masalan aldash aniqlangan bo'lsa).
    #: O'chirilmaydi — bekor qilingan sertifikat ham tarix.
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "Sertifikat"
        verbose_name_plural = "Sertifikatlar"
        ordering = ['-issued_at']
        unique_together = ('user', 'quiz')

    def __str__(self):
        return f"{self.code} — {self.full_name or self.user.username}"

    @property
    def is_valid(self) -> bool:
        return self.revoked_at is None

    @property
    def holder_name(self) -> str:
        return self.full_name or self.user.username


class MentorMessage(models.Model):
    """
    AI Mentor suhbati.

    NEGA SAQLANADI (uchta sabab):
      1. Kontekst — model oldingi savollarni ko'rishi kerak. Tarix
         SERVERDA turadi, klientdan qabul qilinmaydi: aks holda o'quvchi
         soxta "assistant" javoblarini yuborib modelni boshqarib olardi.
      2. Cheklov — kunlik va daqiqalik kvota shu jadvaldan sanaladi.
      3. Nazorat — javob sifati va suiiste'molni admin ko'ra oladi.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mentor_messages')
    question = models.TextField()
    answer = models.TextField(blank=True)

    #: Qaysi darsni ko'rayotganda so'ralgani (bo'lmasa None)
    lesson = models.ForeignKey(
        Lesson, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mentor_messages',
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "AI Mentor savoli"
        verbose_name_plural = "AI Mentor savollari"
        ordering = ['-created_at']
        indexes = [
            # Kvota aynan shu ustunlar bo'yicha sanaydi
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.question[:50]}"


class LoginAttempt(models.Model):
    """
    Login urinishi jurnali — brute-force cheklovi shundan hisoblanadi.

    `username` ATAYLAB FK emas: mavjud bo'lmagan nom bilan qilingan
    urinishlarni ham sanash kerak, aks holda hujumchi tasodifiy nomlar
    yozib IP cheklovidan qutulib ketardi.
    """

    class Purpose(models.TextChoices):
        LOGIN = 'LOGIN', "Tizimga kirish"
        RESET = 'RESET', "Parolni tiklash"

    username = models.CharField(max_length=150, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    successful = models.BooleanField(default=False)
    #: Cheklov turlari ARALASHMASLIGI kerak: parol tiklash so'rovi login
    #: hisoblagichini to'ldirib, foydalanuvchini kirishdan mahrum qilmasin.
    purpose = models.CharField(
        max_length=10, choices=Purpose.choices, default=Purpose.LOGIN, db_index=True
    )
    user_agent = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Login urinishi"
        verbose_name_plural = "Login urinishlari"
        ordering = ['-created_at']
        indexes = [
            # Cheklov aynan shu ustunlar bo'yicha sanaydi
            models.Index(fields=['purpose', 'username', 'successful', '-created_at']),
            models.Index(fields=['purpose', 'ip', 'successful', '-created_at']),
        ]

    def __str__(self):
        holat = "muvaffaqiyatli" if self.successful else "xato"
        return f"{self.get_purpose_display()}: {self.username}@{self.ip} — {holat}"


class PasswordReset(models.Model):
    """
    Parolni tiklash kodi.

    Kodning O'ZI saqlanmaydi — faqat SHA-256 xeshi. Baza qo'lga tushsa
    ham tayyor tiklash kodlari ro'yxati bo'lmaydi.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_resets')

    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField(db_index=True)

    #: Bir marta ishlatiladi: to'ldirilgach kod boshqa yaramaydi
    used_at = models.DateTimeField(null=True, blank=True)

    #: Noto'g'ri urinishlar — 6 xonali kodni cheksiz taxmin qilishning
    #: oldini oladi
    attempts = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Parol tiklash kodi"
        verbose_name_plural = "Parol tiklash kodlari"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'used_at']),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.created_at:%d.%m.%Y %H:%M}"
