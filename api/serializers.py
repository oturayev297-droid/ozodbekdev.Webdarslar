"""
API serializerlari
==================

QOIDA — QULFLANGAN MAZMUN SERIALIZERGA UMUMAN TUSHMAYDI.

Shablonli sahifada bu qoida `core.views.lessons` da amalga oshirilgan:
qulflangan darsning nazariyasi, videosi va rasmlari JSON ga qo'shilmaydi.
API da ham AYNAN SHUNDAY. "Frontend yashiradi" degan yondashuv
ishlamaydi — API javobini brauzerning tarmoq bo'limida har kim ko'radi.

Shuning uchun dars serializeri IKKITA: to'liq va qisqartirilgan.
Qaysi biri ishlatilishi `can_access_lesson` bilan hal qilinadi.
"""

from rest_framework import serializers

from billing.dates import format_money
from billing.services import STATUS_LABELS
from core import richtext
from core.models import (
    Category,
    Certificate,
    Challenge,
    Choice,
    Lesson,
    LessonImage,
    MentorMessage,
    Profile,
    Question,
    Quiz,
)


# ══════════════════════════ Darslar ══════════════════════════


class LessonImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    alt = serializers.CharField(source='display_alt', read_only=True)

    class Meta:
        model = LessonImage
        fields = ['id', 'url', 'caption', 'alt', 'order']

    def get_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        url = obj.image.url
        # To'liq manzil: frontend boshqa domenda turadi va nisbiy
        # manzilni o'zining domeniga nisbatan hal qilib, 404 olardi.
        return request.build_absolute_uri(url) if request else url


class LessonListSerializer(serializers.ModelSerializer):
    """
    Ro'yxat uchun. MAZMUN YO'Q — faqat sarlavha va holat.

    Qulflangan dars ham shu ko'rinishda beriladi: o'quvchi nima sotib
    olayotganini bilishi kerak, lekin matnni olmasligi kerak.
    """

    unlocked = serializers.SerializerMethodField()
    completed = serializers.SerializerMethodField()
    has_video = serializers.SerializerMethodField()
    has_text = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'order', 'is_free',
            'unlocked', 'completed', 'has_video', 'has_text',
        ]

    def get_unlocked(self, obj):
        return obj.id in self.context.get('unlocked_ids', set())

    def get_completed(self, obj):
        return obj.id in self.context.get('completed_ids', set())

    def get_has_video(self, obj):
        return bool(obj.video_file or obj.video_url)

    def get_has_text(self, obj):
        return bool((obj.theory or '').strip())


class LessonDetailSerializer(LessonListSerializer):
    """
    To'liq dars. FAQAT ochiq dars uchun ishlatiladi.

    `theory_html` serverda quriladi (`core.richtext.render`): matn
    to'liq ekranlanadi va faqat ruxsat etilgan teglar qoladi. Frontend
    uni `dangerouslySetInnerHTML` ga bemalol bera oladi.
    """

    theory_html = serializers.SerializerMethodField()
    images = LessonImageSerializer(many=True, read_only=True)
    video_url = serializers.SerializerMethodField()
    quiz_id = serializers.SerializerMethodField()

    class Meta(LessonListSerializer.Meta):
        fields = LessonListSerializer.Meta.fields + [
            'theory_html', 'practice_code', 'images', 'video_url', 'quiz_id',
        ]

    def get_theory_html(self, obj):
        return richtext.render(obj.theory)

    def get_video_url(self, obj):
        """
        Video HAVOLASI beriladi, faylning o'zi emas.

        Havola `/lessons/<id>/video/` ga ishora qiladi va u yerda huquq
        QAYTA tekshiriladi. Havolani qo'lga kiritgan begona odam ham
        videoni ololmaydi.
        """
        request = self.context.get('request')
        if obj.video_file:
            path = f'/lessons/{obj.id}/video/'
            return request.build_absolute_uri(path) if request else path
        return obj.video_url or None

    def get_quiz_id(self, obj):
        quiz = getattr(obj, 'quiz', None)
        # Qoralama test o'quvchiga ko'rinmaydi
        if quiz and quiz.is_published:
            return quiz.id
        return None


class LockedLessonSerializer(LessonListSerializer):
    """
    Qulflangan dars. Mazmun MAYDONLARI umuman yo'q.

    Bo'sh satr bilan qaytarish ham mumkin edi, lekin maydonning
    o'zini olib tashlash aniqroq: kelajakda kimdir "bu yerda nima
    bo'lishi kerak edi" deb o'ylab qolmaydi.
    """

    class Meta(LessonListSerializer.Meta):
        fields = LessonListSerializer.Meta.fields


class ModuleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    order = serializers.IntegerField()
    lessons = LessonListSerializer(many=True)


class CategorySerializer(serializers.ModelSerializer):
    total_lessons = serializers.IntegerField(read_only=True)
    free_lessons = serializers.IntegerField(read_only=True)
    completed_lessons = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description',
            'total_lessons', 'free_lessons', 'completed_lessons',
        ]


# ══════════════════════════ Testlar ══════════════════════════


class ChoiceSerializer(serializers.ModelSerializer):
    """
    DIQQAT — `is_correct` MAYDONI YO'Q va hech qachon qo'shilmasin.

    Bu qoida butun loyihaning eng muhim qoidalaridan biri: to'g'ri
    javob klientga yuborilsa, test ma'nosini yo'qotadi va sertifikat
    ham qadrsizlanadi. Ball faqat serverda hisoblanadi.
    """

    class Meta:
        model = Choice
        fields = ['id', 'text']


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'choices']


class QuizListSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    category = serializers.CharField(source='lesson.module.category.name', read_only=True)
    question_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'time_limit', 'lesson_id',
            'lesson_title', 'category', 'question_count',
        ]


class QuizDetailSerializer(QuizListSerializer):
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta(QuizListSerializer.Meta):
        fields = QuizListSerializer.Meta.fields + ['questions']


class QuizSubmitSerializer(serializers.Serializer):
    """
    Topshirish. KLIENT FAQAT TANLOV ID LARINI yuboradi.

    Ball, to'g'ri javoblar soni va foiz — hammasi serverda hisoblanadi.
    Klientdan kelgan har qanday "score" e'tiborsiz qoldiriladi.
    """

    answers = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="{savol_id: tanlov_id}",
    )

    def validate_answers(self, value):
        if not value:
            raise serializers.ValidationError("Javoblar bo'sh.")
        return value


# ══════════════════════════ Obuna va profil ══════════════════════════


class SubscriptionStateSerializer(serializers.Serializer):
    """`billing.services.SubscriptionState` ning API ko'rinishi."""

    status = serializers.CharField()
    status_label = serializers.SerializerMethodField()
    active = serializers.BooleanField()
    current_period_end = serializers.DateTimeField(allow_null=True)
    days_left = serializers.IntegerField()
    in_grace = serializers.BooleanField()
    in_hold = serializers.BooleanField()

    def get_status_label(self, obj):
        return STATUS_LABELS.get(obj.status, obj.status)


class PlanOptionSerializer(serializers.Serializer):
    months = serializers.IntegerField()
    amount_tiyin = serializers.IntegerField()
    amount_display = serializers.CharField()


class ProfileSerializer(serializers.Serializer):
    """Joriy foydalanuvchi. `/api/v1/auth/me/` javobining asosi."""

    id = serializers.IntegerField(source='user.id')
    username = serializers.CharField(source='user.username')
    email = serializers.EmailField(source='user.email')
    full_name = serializers.CharField()
    level = serializers.IntegerField()
    is_staff = serializers.BooleanField(source='user.is_staff')
    is_approved = serializers.BooleanField()
    rejection_reason = serializers.CharField()
    telegram_linked = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    def get_telegram_linked(self, obj):
        return bool(obj.telegram_chat_id)

    def get_avatar(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class CertificateSerializer(serializers.ModelSerializer):
    pdf_url = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            'code', 'quiz_title', 'category_name', 'score_percentage',
            'full_name', 'issued_at', 'is_valid', 'pdf_url',
        ]

    def get_is_valid(self, obj):
        return obj.revoked_at is None

    def get_pdf_url(self, obj):
        request = self.context.get('request')
        path = f'/certificates/{obj.code}/pdf/'
        return request.build_absolute_uri(path) if request else path


# ══════════════════════════ Autentifikatsiya ══════════════════════════


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={'input_type': 'password'}, trim_whitespace=False)


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, trim_whitespace=False)
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=255)


class MentorAskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=2000)
    lesson_id = serializers.IntegerField(required=False, allow_null=True)


# ══════════════════════════ Kod muharriri ══════════════════════════


class ChallengeListSerializer(serializers.ModelSerializer):
    """
    Topshiriqlar ro'yxati.

    DIQQAT — `solution_code` MAYDONI YO'Q va bo'lmasligi kerak. Yechim
    alohida endpoint orqali, o'quvchi ATAYLAB so'raganda beriladi.
    Ro'yxatga qo'shilsa, u sahifa yuklanishida javobga tushib qolardi
    va topshiriqning ma'nosi qolmasdi.
    """

    class Meta:
        model = Challenge
        fields = ['id', 'title', 'language', 'difficulty', 'order']


class ChallengeDetailSerializer(ChallengeListSerializer):
    description_html = serializers.SerializerMethodField()
    has_solution = serializers.SerializerMethodField()

    class Meta(ChallengeListSerializer.Meta):
        fields = ChallengeListSerializer.Meta.fields + [
            'description_html', 'initial_code', 'has_solution',
        ]

    def get_description_html(self, obj):
        return richtext.render(obj.description)

    def get_has_solution(self, obj):
        """Yechim BOR-YO'QLIGI aytiladi, yechimning O'ZI emas."""
        return bool((obj.solution_code or '').strip())


# ══════════════════════════ Profil ══════════════════════════


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Profilni tahrirlash.

    `image` bu yerda YO'Q — fayl yuklash JSON bilan bir so'rovda
    ketmaydi. Rasm alohida endpoint orqali `multipart/form-data`
    bilan yuboriladi.
    """

    class Meta:
        model = Profile
        fields = ['full_name', 'bio']


class MentorMessageSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source='lesson.title', read_only=True, default='')

    class Meta:
        model = MentorMessage
        fields = ['id', 'question', 'answer', 'lesson_title', 'created_at']
