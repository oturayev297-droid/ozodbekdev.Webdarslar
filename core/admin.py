from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from django.db.models import Count, Q
from .models import Category, Module, Lesson, Challenge, Quiz, Question, Choice, Project, Profile, NewStudent, UserProgress

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
    list_display = ('title', 'difficulty', 'order')
    list_filter = ('difficulty',)
    search_fields = ('title', 'description')

# Lesson
try:
    admin.site.unregister(Lesson)
except admin.sites.NotRegistered:
    pass
@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'order')
    list_filter = ('module__category', 'module')
    search_fields = ('title', 'theory')

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
    list_display = ('title', 'lesson', 'time_limit')
    inlines = [QuestionInline]

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
