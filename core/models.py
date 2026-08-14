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
    theory = models.TextField(default="", help_text="Nazariy ma'lumotlar uchun (HTML/Markdown qo'llab-quvvatlaydi)")
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

class Quiz(models.Model):
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='quiz')
    title = models.CharField(max_length=200)
    time_limit = models.PositiveIntegerField(default=20, help_text="Testni topshirish vaqti (minutda)")

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
