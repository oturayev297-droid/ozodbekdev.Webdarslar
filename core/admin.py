from django.contrib import admin, messages
from django.contrib.admin.sites import AlreadyRegistered
from django.urls import reverse
from django.db.models import Count, Q
from django.utils.html import format_html
from .models import Category, Module, Lesson, Challenge, Quiz, Question, Choice, Project, Profile, NewStudent, UserProgress, LoginAttempt, Certificate, MentorMessage

# Helper function to safely register models
def safe_register(model, admin_class=None):
    try:
        admin.site.unregister(model)
    except admin.sites.NotRegistered:
        pass

    if admin_class:
        admin.site.register(model, admin_class)
    else:
        admin.site.register(model)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}

# For other models, we use the safe registration pattern by checking first
# or catching the error. Standard @admin.register decorator isn't safe against
# double-registration if the file is imported twice.
# So we use the try-unregister-then-register pattern.

# Module
try:
    admin.site.unregister(Module)
except admin.sites.NotRegistered:
    pass
@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'order')
    list_filter = ('category',)
    search_fields = ('title',)

# Challenge
try:
    admin.site.unregister(Challenge)
except admin.sites.NotRegistered:
    pass
@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ('title', 'language', 'difficulty', 'order')
    list_filter = ('language', 'difficulty')
    search_fields = ('title', 'description')
    list_editable = ('order',)
    fieldsets = (
        ("Asosiy", {'fields': ('title', 'language', 'difficulty', 'order')}),
        ("Topshiriq", {'fields': ('description', 'initial_code')}),
        ("Yechim", {
            'fields': ('solution_code',),
            'description': (
                "Yechim sahifa HTML iga <b>chiqarilmaydi</b> — uni faqat "
                "<code>/editor/&lt;id&gt;/solution/</code> so'ralganda beriladi."
            ),
        }),
    )

# Lesson
try:
    admin.site.unregister(Lesson)
except admin.sites.NotRegistered:
    pass
@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'order', 'is_free_badge', 'has_video')
    list_filter = ('is_free', 'module__category', 'module')
    search_fields = ('title', 'theory')
    list_editable = ('order',)
    actions = ['make_free', 'make_paid']

    @admin.display(description="Kirish", ordering='is_free', boolean=False)
    def is_free_badge(self, obj):
        if obj.is_free:
            return format_html(
                '<span style="background:#10b981;color:#fff;padding:2px 8px;'
                'border-radius:10px;font-size:11px;font-weight:700">BEPUL</span>'
            )
        return format_html(
            '<span style="background:#6366f1;color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:700">OBUNA</span>'
        )

    @admin.display(description="Video", boolean=True)
    def has_video(self, obj):
        return bool(obj.video_file or obj.video_url)

    @admin.action(description="BEPUL qilish (obunasiz ochiq)")
    def make_free(self, request, queryset):
        count = queryset.update(is_free=True)
        self.message_user(request, f"{count} ta dars bepul qilindi.")

    @admin.action(description="OBUNA talab qilsin")
    def make_paid(self, request, queryset):
        count = queryset.update(is_free=False)
        self.message_user(request, f"{count} ta dars obunaga o'tkazildi.")

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2

class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    inlines = [ChoiceInline]

# Question
try:
    admin.site.unregister(Question)
except admin.sites.NotRegistered:
    pass
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    inlines = [ChoiceInline]
    list_display = ('text', 'quiz')
    search_fields = ('text',)

# Quiz
try:
    admin.site.unregister(Quiz)
except admin.sites.NotRegistered:
    pass
@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """
    Testlar. Qoralamalar (`is_published=False`) o'quvchiga ko'rinmaydi —
    `generate_quizzes` yozgan savollar shu holatda keladi.
    """

    list_display = ('title', 'lesson', 'state', 'question_count', 'time_limit', 'created_at')
    list_filter = ('is_published', 'is_generated', 'lesson__module__category')
    search_fields = ('title', 'lesson__title')
    inlines = [QuestionInline]
    actions = ['action_publish', 'action_unpublish']
    readonly_fields = ('is_generated', 'created_at', 'review_help')
    fields = ('review_help', 'lesson', 'title', 'time_limit',
              'is_published', 'is_generated', 'created_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'lesson__module__category'
        ).annotate(_questions=Count('questions', distinct=True))

    @admin.display(description="Tekshirish")
    def review_help(self, obj):
        if obj and obj.is_generated and not obj.is_published:
            return format_html(
                "<b style=\"color:#b45309\">Bu testni model yozgan va u hali "
                "nashr qilinmagan.</b><br><br>"
                "Nashr qilishdan oldin har savolni o'qib chiqing:<br>"
                "&bull; savol darsda haqiqatan o'tilgan mavzugami?<br>"
                "&bull; to'g'ri javob rostdan to'g'rimi?<br>"
                "&bull; boshqa variantlar aniq noto'g'rimi?<br><br>"
                "Tayyor bo'lsa ro'yxat sahifasidan «Nashr qilish» amalini tanlang."
            )
        return format_html(
            "Qoralama qilish uchun <b>Nashr qilingan</b> belgisini olib tashlang — "
            "o'quvchi testni ko'rmay qoladi."
        )

    @admin.display(description="Holat", ordering='is_published')
    def state(self, obj):
        if not obj.is_published:
            label, color = ("QORALAMA (model)" if obj.is_generated else "QORALAMA"), '#f59e0b'
        else:
            label, color = "NASHRDA", '#10b981'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:700">{}</span>',
            color, label,
        )

    @admin.display(description="Savollar", ordering='_questions')
    def question_count(self, obj):
        return getattr(obj, '_questions', 0)

    @admin.action(description="Nashr qilish (o'quvchiga ochiladi)")
    def action_publish(self, request, queryset):
        empty = [q.title for q in queryset if not q.questions.exists()]
        if empty:
            self.message_user(
                request,
                "Savoli yo'q testni nashr qilib bo'lmaydi: " + ", ".join(empty[:5]),
                level=messages.ERROR,
            )
            queryset = queryset.exclude(questions__isnull=True)

        count = queryset.update(is_published=True)
        if count:
            self.message_user(request, f"{count} ta test nashr qilindi.")

    @admin.action(description="Nashrdan olish (qoralamaga qaytarish)")
    def action_unpublish(self, request, queryset):
        count = queryset.update(is_published=False)
        self.message_user(request, f"{count} ta test qoralamaga qaytarildi.")

# Project
try:
    admin.site.unregister(Project)
except admin.sites.NotRegistered:
    pass
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'difficulty', 'tech_stack', 'order')
    list_filter = ('difficulty',)
    search_fields = ('title', 'tech_stack')

# Profile
try:
    admin.site.unregister(Profile)
except admin.sites.NotRegistered:
    pass
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'level')
    search_fields = ('user__username', 'full_name')

# NewStudent
try:
    admin.site.unregister(NewStudent)
except admin.sites.NotRegistered:
    pass
@admin.register(NewStudent)
class NewStudentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'get_username', 'get_email', 'get_date_joined', 'get_progress')
    search_fields = ('full_name', 'user__username', 'user__email')
    ordering = ('-user__date_joined',)
    
    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    
    def get_date_joined(self, obj):
        return obj.user.date_joined
    get_date_joined.short_description = 'Ro\'yxatdan o\'tgan vaqti'

    def get_progress(self, obj):
        total_lessons = Lesson.objects.count()
        if total_lessons == 0:
            return "0%"
        completed_lessons = UserProgress.objects.filter(user=obj.user, is_completed=True).count()
        percentage = int((completed_lessons / total_lessons) * 100)
        return f"{percentage}%"
    get_progress.short_description = 'O\'zlashtirish Foizi'


# Login urinishlari — faqat o'qish uchun jurnal
try:
    admin.site.unregister(LoginAttempt)
except admin.sites.NotRegistered:
    pass
@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """
    Xavfsizlik jurnali. Qo'lda o'zgartirilmaydi — qulflash mantig'i
    aynan shu yozuvlardan hisoblanadi, ularni tahrirlash cheklovni
    aylanib o'tish yo'li bo'lardi.
    """

    list_display = ('created_at', 'purpose', 'username', 'ip', 'result', 'short_agent')
    list_filter = ('purpose', 'successful', 'created_at')
    search_fields = ('username', 'ip')
    date_hierarchy = 'created_at'

    @admin.display(description="Natija", ordering='successful')
    def result(self, obj):
        if obj.successful:
            return format_html(
                '<span style="background:#10b981;color:#fff;padding:2px 8px;'
                'border-radius:10px;font-size:11px;font-weight:700">OK</span>'
            )
        return format_html(
            '<span style="background:#ef4444;color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:700">XATO</span>'
        )

    @admin.display(description="Brauzer")
    def short_agent(self, obj):
        return (obj.user_agent[:60] + '...') if len(obj.user_agent) > 60 else obj.user_agent

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# Sertifikatlar
try:
    admin.site.unregister(Certificate)
except admin.sites.NotRegistered:
    pass
@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    """
    Berilgan sertifikatlar. Qo'lda YARATILMAYDI va o'zgartirilmaydi —
    ular test natijasidan avtomatik chiqadi.

    Bekor qilish mumkin (aldash aniqlansa), lekin o'chirib bo'lmaydi:
    bekor qilingan sertifikat ham tarix, va tekshirish sahifasi uni
    "bekor qilingan" deb ko'rsatishi kerak. O'chirilsa "topilmadi"
    chiqib, sabab noma'lum bo'lib qolardi.
    """

    list_display = ('code', 'holder', 'quiz_title', 'score_percentage', 'issued_at', 'status')
    list_filter = ('category_name', 'issued_at')
    search_fields = ('code', 'full_name', 'user__username', 'user__email', 'quiz_title')
    date_hierarchy = 'issued_at'
    actions = ['action_revoke', 'action_restore']

    readonly_fields = (
        'code', 'user', 'quiz', 'score_percentage', 'full_name', 'quiz_title',
        'category_name', 'issued_at', 'revoked_at', 'status', 'verify_link', 'notice',
    )
    fields = (
        'notice', 'code', 'verify_link', 'status', 'user', 'full_name',
        'quiz', 'quiz_title', 'category_name', 'score_percentage',
        'issued_at', 'revoked_at', 'revoke_reason',
    )

    @admin.display(description="Diqqat")
    def notice(self, obj):
        return format_html(
            "Bekor qilish uchun <b>Bekor qilish sababi</b> ni to'ldirib saqlang, "
            "so'ng ro'yxatdan <i>\"Bekor qilish\"</i> amalini tanlang.<br>"
            "Sertifikatdagi ball ATAYLAB o'zgarmaydi — test qayta topshirilsa ham "
            "berilgan hujjat qayta yozilmaydi."
        )

    @admin.display(description="Egasi", ordering='full_name')
    def holder(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.holder_name)

    @admin.display(description="Tekshirish havolasi")
    def verify_link(self, obj):
        url = f"{reverse('verify_certificate')}?code={obj.code}"
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)

    @admin.display(description="Holat")
    def status(self, obj):
        if obj.is_valid:
            return format_html(
                '<span style="background:#10b981;color:#fff;padding:2px 8px;'
                'border-radius:10px;font-size:11px;font-weight:700">AMALDA</span>'
            )
        return format_html(
            '<span style="background:#ef4444;color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:700">BEKOR</span>'
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'quiz')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Bekor qilish (sabab to'ldirilgan bo'lishi kerak)")
    def action_revoke(self, request, queryset):
        from django.utils import timezone as tz
        done = 0
        for cert in queryset:
            if not cert.revoke_reason.strip():
                self.message_user(
                    request,
                    f"{cert.code}: avval \"Bekor qilish sababi\" ni to'ldiring.",
                    level=messages.ERROR,
                )
                continue
            if cert.revoked_at:
                continue
            cert.revoked_at = tz.now()
            cert.save(update_fields=['revoked_at'])
            done += 1
        if done:
            self.message_user(request, f"{done} ta sertifikat bekor qilindi.")

    @admin.action(description="Bekor qilishni qaytarish")
    def action_restore(self, request, queryset):
        count = queryset.filter(revoked_at__isnull=False).update(revoked_at=None)
        self.message_user(request, f"{count} ta sertifikat tiklandi.")


# AI Mentor suhbatlari — faqat o'qish
try:
    admin.site.unregister(MentorMessage)
except admin.sites.NotRegistered:
    pass
@admin.register(MentorMessage)
class MentorMessageAdmin(admin.ModelAdmin):
    """
    Javob sifatini va suiiste'molni kuzatish uchun. Qo'lda
    yaratilmaydi va tahrirlanmaydi — bu suhbat yozuvi.
    """

    list_display = ('created_at', 'user', 'short_question', 'lesson', 'answered')
    list_filter = ('created_at', 'lesson__module__category')
    search_fields = ('user__username', 'question', 'answer')
    date_hierarchy = 'created_at'
    readonly_fields = ('user', 'question', 'answer', 'lesson', 'created_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'lesson')

    @admin.display(description="Savol")
    def short_question(self, obj):
        return (obj.question[:70] + '...') if len(obj.question) > 70 else obj.question

    @admin.display(description="Javob berildi", boolean=True)
    def answered(self, obj):
        return bool(obj.answer)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
