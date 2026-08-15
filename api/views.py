"""
API ko'rinishlari
=================

QOIDA — BIZNES MANTIQ TAKRORLANMAYDI. Har bir amal mavjud modullarga
topshiriladi:

    ball hisoblash   -> core.quiz_scoring.score_quiz
    obuna uzaytirish -> billing.services.extend_subscription
    to'lov so'rovi   -> billing.payment_requests
    darvoza          -> core.approval + billing.gating
    AI mentor        -> core.ai_mentor.ask

API bu funksiyalarni CHAQIRADI. Nusxa yozilsa, shablonli sahifa bilan
API ertami-kechmi bir-biriga to'g'ri kelmay qolardi va qaysi biri
to'g'ri ekani bilinmasdi.
"""

import logging

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Count, Prefetch
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing import payment_requests as pr
from billing import services, telegram
from billing.dates import ALLOWED_MONTHS, format_money
from billing.gating import can_access_lesson, can_access_quiz
from core import ai_mentor, lockout, quiz_scoring
from core import password_reset as pwreset
from core.approval import is_approved
from core.models import Category, Certificate, Lesson, Profile, Quiz, QuizResult, UserProgress

from .permissions import IsApproved
from .serializers import (
    CategorySerializer,
    CertificateSerializer,
    LessonDetailSerializer,
    LessonListSerializer,
    LockedLessonSerializer,
    LoginSerializer,
    MentorAskSerializer,
    PlanOptionSerializer,
    ProfileSerializer,
    QuizDetailSerializer,
    QuizListSerializer,
    QuizSubmitSerializer,
    RegisterSerializer,
    SubscriptionStateSerializer,
)

logger = logging.getLogger(__name__)


def _profile(user) -> Profile:
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _me_payload(request) -> dict:
    """`/auth/me/` va login javobi uchun umumiy ma'lumot."""
    profile = _profile(request.user)
    return {
        'user': ProfileSerializer(profile, context={'request': request}).data,
        'subscription': SubscriptionStateSerializer(services.get_state(request.user)).data,
    }


# ══════════════════════════ Autentifikatsiya ══════════════════════════


@api_view(['GET'])
@permission_classes([AllowAny])
def csrf(request):
    """
    CSRF tokenini beradi va cookie o'rnatadi.

    NEGA KERAK: frontend alohida domenda turadi va Django shablonidan
    token ololmaydi. Sessiya autentifikatsiyasi ishlashi uchun
    frontend avval shu manzilni chaqiradi, keyin tokenni
    `X-CSRFToken` sarlavhasida yuboradi.
    """
    return Response({'csrfToken': get_token(request)})


class LoginView(APIView):
    """
    Tizimga kirish.

    Brute-force himoyasi shablonli login bilan BIR XIL modul orqali
    (`core.lockout`) — ikkinchi nusxa yozilsa, hujumchi API orqali
    cheklovsiz urinib ko'rardi.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username'].strip()
        password = serializer.validated_data['password']
        ip = lockout.client_ip(request)

        # DARVOZA: parolni tekshirishdan OLDIN
        locked, retry_after, _ = lockout.check_locked(username, ip)
        if locked:
            return Response(
                {'detail': lockout.lockout_message(retry_after), 'code': 'LOCKED'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            lockout.record_failure(request, username)
            return Response(
                {'detail': "Login yoki parol noto'g'ri.", 'code': 'INVALID_CREDENTIALS'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        lockout.record_success(request, user)
        login(request, user)
        return Response(_me_payload(request))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(APIView):
    """
    Ro'yxatdan o'tish.

    Yangi hisob RUXSATSIZ yaratiladi (`Profile.is_approved=False`) —
    shablonli ro'yxatdan o'tish bilan bir xil. API orqali ochiq hisob
    yaratib bo'lmasligi kerak.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        username = data['username'].strip()
        email = data['email'].strip().lower()

        if User.objects.filter(username__iexact=username).exists():
            return Response(
                {'username': ["Ushbu foydalanuvchi nomi band."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {'email': ["Bu email allaqachon ro'yxatdan o'tgan."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(data['password'])
        except ValidationError as exc:
            return Response({'password': exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, email=email, password=data['password'])
        profile = _profile(user)
        profile.full_name = (data.get('full_name') or '').strip()
        profile.save(update_fields=['full_name'])

        login(request, user)
        logger.info("Yangi ro'yxatdan o'tish (API): %s (ruxsat kutilmoqda)", username)

        # Xabar ketmasa ham ro'yxatdan o'tish buzilmaydi
        try:
            telegram.notify_new_registration(user)
        except Exception:
            logger.exception("Yangi ro'yxatdan o'tish haqida xabar yuborilmadi")

        return Response(_me_payload(request), status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """
    Joriy foydalanuvchi.

    RUXSAT TEKSHIRILMAYDI — bu manzil aynan ruxsat holatini bilish
    uchun kerak. Ruxsatsiz odam ham o'z holatini ko'ra olishi kerak,
    aks holda frontend "kutish" ekranini ko'rsata olmasdi.
    """
    return Response(_me_payload(request))


class PasswordResetRequestView(APIView):
    """Parol tiklash — 1-qadam. Javob email bor-yo'qligidan qat'i nazar bir xil."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get('email') or '').strip()
        ip = lockout.client_ip(request)

        throttled, retry_after = lockout.check_reset_throttle(ip)
        if throttled:
            return Response(
                {'detail': lockout.reset_throttle_message(retry_after)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        lockout.record_reset_request(request, email)
        return Response({'detail': pwreset.request_reset(email)})


class PasswordResetConfirmView(APIView):
    """Parol tiklash — 2-qadam."""

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            message = pwreset.confirm_reset(
                (request.data.get('email') or '').strip(),
                (request.data.get('code') or '').strip(),
                request.data.get('new_password') or '',
            )
        except pwreset.ResetError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': message})


# ══════════════════════════ Kurslar va darslar ══════════════════════════


class CourseListView(APIView):
    """Bo'limlar ro'yxati — dars sonlari va o'zlashtirish bilan."""

    permission_classes = [IsAuthenticated, IsApproved]

    def get(self, request):
        completed_ids = set(
            UserProgress.objects.filter(user=request.user, is_completed=True)
            .values_list('lesson_id', flat=True)
        )

        categories = Category.objects.prefetch_related('modules__lessons').order_by('name')

        data = []
        for category in categories:
            lessons = [
                lesson
                for module in category.modules.all()
                for lesson in module.lessons.all()
            ]
            if not lessons:
                # Bo'sh bo'limni bermaymiz — frontend uni bosib, bo'sh
                # ro'yxatga tushib qolardi
                continue

            payload = CategorySerializer(category).data
            payload['total_lessons'] = len(lessons)
            payload['free_lessons'] = sum(1 for l in lessons if l.is_free)
            payload['completed_lessons'] = sum(1 for l in lessons if l.id in completed_ids)
            data.append(payload)

        return Response(data)


class CourseDetailView(APIView):
    """Bitta bo'lim: modullar va ular ichidagi darslar ro'yxati."""

    permission_classes = [IsAuthenticated, IsApproved]

    def get(self, request, slug):
        category = get_object_or_404(
            Category.objects.prefetch_related(
                Prefetch('modules__lessons', queryset=Lesson.objects.order_by('order'))
            ),
            slug=slug,
        )

        completed_ids = set(
            UserProgress.objects.filter(user=request.user, is_completed=True)
            .values_list('lesson_id', flat=True)
        )
        subscribed = services.get_state(request.user).active

        modules = []
        unlocked_ids = set()
        for module in category.modules.all().order_by('order'):
            lessons = list(module.lessons.all())
            for lesson in lessons:
                if lesson.is_free or subscribed:
                    unlocked_ids.add(lesson.id)
            modules.append({'id': module.id, 'title': module.title,
                            'order': module.order, 'lessons': lessons})

        context = {
            'request': request,
            'completed_ids': completed_ids,
            'unlocked_ids': unlocked_ids,
        }

        return Response({
            'category': CategorySerializer(category).data,
            'modules': [
                {
                    'id': m['id'],
                    'title': m['title'],
                    'order': m['order'],
                    'lessons': LessonListSerializer(m['lessons'], many=True, context=context).data,
                }
                for m in modules
            ],
        })


class LessonDetailView(APIView):
    """
    Bitta dars.

    QULFLANGAN DARS MAZMUNI QAYTARILMAYDI — sarlavha va holat qoladi,
    matn, video va rasmlar javobga umuman tushmaydi. "Frontend
    yashiradi" degan yondashuv ishlamaydi: API javobi brauzerning
    tarmoq bo'limida ochiq ko'rinadi.
    """

    permission_classes = [IsAuthenticated, IsApproved]

    def get(self, request, pk):
        lesson = get_object_or_404(
            Lesson.objects.select_related('module__category', 'quiz').prefetch_related('images'),
            pk=pk,
        )

        completed_ids = set(
            UserProgress.objects.filter(user=request.user, is_completed=True)
            .values_list('lesson_id', flat=True)
        )
        allowed = can_access_lesson(request.user, lesson)

        context = {
            'request': request,
            'completed_ids': completed_ids,
            'unlocked_ids': {lesson.id} if allowed else set(),
        }

        serializer_class = LessonDetailSerializer if allowed else LockedLessonSerializer
        data = serializer_class(lesson, context=context).data
        data['category'] = lesson.module.category.name
        data['category_slug'] = lesson.module.category.slug

        if not allowed:
            data['locked_reason'] = "Bu dars obuna bilan ochiladi."
            return Response(data, status=status.HTTP_402_PAYMENT_REQUIRED)

        return Response(data)


class LessonCompleteView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def post(self, request, pk):
        lesson = get_object_or_404(Lesson, pk=pk)

        if not can_access_lesson(request.user, lesson):
            return Response(
                {'detail': "Bu dars obuna bilan ochiladi.", 'code': 'SUBSCRIPTION_REQUIRED'},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        progress, created = UserProgress.objects.get_or_create(
            user=request.user, lesson=lesson, defaults={'is_completed': True}
        )
        if not created and not progress.is_completed:
            progress.is_completed = True
            progress.save(update_fields=['is_completed'])

        total = Lesson.objects.count()
        done = UserProgress.objects.filter(user=request.user, is_completed=True).count()
        return Response({
            'completed': True,
            'total_lessons': total,
            'completed_lessons': done,
        })


# ══════════════════════════ Testlar ══════════════════════════


def _visible_quizzes(user):
    """
    Qoralama testlar o'quvchiga ko'rinmaydi.

    `core.views._visible_quizzes` bilan bir xil qoida. Ikkalasi bitta
    joyda bo'lgani ma'qul edi, lekin API `core.views` ni import qilsa
    aylanma bog'liqlik paydo bo'lardi.
    """
    qs = Quiz.objects.select_related('lesson__module__category')
    if user.is_staff:
        return qs
    return qs.filter(is_published=True)


class QuizListView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def get(self, request):
        quizzes = (
            _visible_quizzes(request.user)
            .annotate(question_count=Count('questions'))
            .order_by('lesson__module__order', 'lesson__order')
        )
        results = {
            r.quiz_id: r
            for r in QuizResult.objects.filter(user=request.user)
        }

        data = []
        for quiz in quizzes:
            row = QuizListSerializer(quiz).data
            row['unlocked'] = can_access_quiz(request.user, quiz)
            result = results.get(quiz.id)
            row['best_score'] = result.score_percentage if result else None
            row['attempts'] = result.attempts if result else 0
            data.append(row)

        return Response(data)


class QuizDetailView(APIView):
    """
    Savollar va variantlar.

    TO'G'RI JAVOB YUBORILMAYDI — `ChoiceSerializer` da `is_correct`
    maydoni umuman yo'q.
    """

    permission_classes = [IsAuthenticated, IsApproved]

    def get(self, request, pk):
        quiz = get_object_or_404(
            _visible_quizzes(request.user).annotate(question_count=Count('questions')),
            pk=pk,
        )

        if not can_access_quiz(request.user, quiz):
            return Response(
                {'detail': "Bu test obuna bilan ochiladi.", 'code': 'SUBSCRIPTION_REQUIRED'},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        return Response(QuizDetailSerializer(quiz, context={'request': request}).data)


class QuizSubmitView(APIView):
    """Topshirish. Ball `core.quiz_scoring` da, serverda hisoblanadi."""

    permission_classes = [IsAuthenticated, IsApproved]

    def post(self, request, pk):
        quiz = get_object_or_404(_visible_quizzes(request.user), pk=pk)

        if not can_access_quiz(request.user, quiz):
            return Response(
                {'detail': "Bu test obuna bilan ochiladi.", 'code': 'SUBSCRIPTION_REQUIRED'},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        serializer = QuizSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            outcome = quiz_scoring.score_quiz(
                request.user, quiz, serializer.validated_data['answers']
            )
        except quiz_scoring.ScoringError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        certificate = outcome.pop('certificate')
        outcome['certificate'] = (
            CertificateSerializer(certificate, context={'request': request}).data
            if certificate else None
        )
        return Response(outcome)


# ══════════════════════════ Obuna ══════════════════════════


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_state(request):
    """Obuna holati va mavjud tariflar."""
    plan = services.get_plan()
    options = [
        {
            'months': m,
            'amount_tiyin': plan.price_for(m),
            'amount_display': format_money(plan.price_for(m)),
        }
        for m in ALLOWED_MONTHS
    ]

    open_request = pr.get_open_request(request.user)

    return Response({
        'state': SubscriptionStateSerializer(services.get_state(request.user)).data,
        'plan': {
            'name': plan.name,
            'price_per_month_tiyin': plan.price_per_month_tiyin,
            'price_display': format_money(plan.price_per_month_tiyin),
            'grace_days': plan.grace_days,
        },
        'options': PlanOptionSerializer(options, many=True).data,
        'open_request': {
            'id': open_request.id,
            'months': open_request.months,
            'amount_display': format_money(open_request.amount_tiyin),
            'status': open_request.status,
            'status_label': open_request.get_status_display(),
        } if open_request else None,
    })


class PaymentRequestCreateView(APIView):
    """To'lov so'rovi. Summa SERVERDA hisoblanadi — klientdan olinmaydi."""

    permission_classes = [IsAuthenticated, IsApproved]

    def post(self, request):
        try:
            months = int(request.data.get('months', 1))
        except (TypeError, ValueError):
            return Response({'detail': "Muddat noto'g'ri."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            obj = pr.create_request(request.user, months)
        except services.BillingError as exc:
            return Response({'detail': str(exc)}, status=exc.status)

        return Response(
            {
                'id': obj.id,
                'months': obj.months,
                'amount_display': format_money(obj.amount_tiyin),
                'status': obj.status,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentReceiptView(APIView):
    """«Chekni yubordim» — kutish rejimini yoqadi."""

    permission_classes = [IsAuthenticated, IsApproved]

    def post(self, request):
        try:
            obj = pr.mark_receipt_sent(request.user, request.data.get('source'))
        except services.BillingError as exc:
            return Response({'detail': str(exc)}, status=exc.status)
        return Response({'id': obj.id, 'status': obj.status})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsApproved])
def payment_card(request):
    """
    Karta rekvizitlari.

    FAQAT so'rovi «Karta berildi» holatidagi o'quvchiga ko'rinadi —
    `billing.payment_requests.get_card_for_user` shu shartni
    tekshiradi va boshqa yo'l qoldirilmagan.
    """
    return Response(pr.get_card_for_user(request.user))


# ══════════════════════════ Sertifikatlar ══════════════════════════


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsApproved])
def my_certificates(request):
    certificates_qs = Certificate.objects.filter(user=request.user).order_by('-issued_at')
    return Response(
        CertificateSerializer(certificates_qs, many=True, context={'request': request}).data
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_certificate(request):
    """
    Sertifikatni tekshirish — OCHIQ manzil.

    Ish beruvchi tizimda hisobga ega emas, shuning uchun bu yerda
    autentifikatsiya talab qilinmaydi. Faqat kod bo'yicha qidiriladi
    va shaxsiy ma'lumot berilmaydi.
    """
    code = (request.query_params.get('code') or '').strip().upper()
    if not code:
        return Response({'found': False, 'detail': 'Kod berilmadi.'})

    certificate = Certificate.objects.filter(code=code).first()
    if certificate is None:
        return Response({'found': False, 'detail': 'Bunday sertifikat topilmadi.'})

    return Response({
        'found': True,
        'valid': certificate.revoked_at is None,
        'holder': certificate.full_name or certificate.user.username,
        'quiz_title': certificate.quiz_title,
        'category': certificate.category_name,
        'score': certificate.score_percentage,
        'issued_at': certificate.issued_at,
        'revoke_reason': certificate.revoke_reason if certificate.revoked_at else '',
    })


# ══════════════════════════ AI Mentor ══════════════════════════


class MentorAskView(APIView):
    """
    Savol berish.

    Suhbat tarixi SERVERDA saqlanadi va klientdan qabul qilinmaydi —
    aks holda o'quvchi soxta "assistant" javoblarini yuborib modelni
    boshqarib olardi (prompt injection). Bu qoida `core.ai_mentor` da.
    """

    permission_classes = [IsAuthenticated, IsApproved]

    def post(self, request):
        serializer = MentorAskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # QULFLANGAN DARS KONTEKSTI RAD ETILADI. Aks holda obunasiz
        # o'quvchi qulflangan dars raqamini yuborib, uning mazmunini
        # model orqali bilib olardi.
        lesson = None
        lesson_id = serializer.validated_data.get('lesson_id')
        if lesson_id:
            lesson = (
                Lesson.objects.filter(id=lesson_id)
                .select_related('module__category')
                .first()
            )
            if lesson and not can_access_lesson(request.user, lesson):
                lesson = None

        try:
            result = ai_mentor.ask(
                request.user, serializer.validated_data['question'], lesson=lesson
            )
        except ai_mentor.MentorError as exc:
            # `MentorError.status` cheklovda 429, boshqa holatda 400/503
            return Response(
                {'detail': getattr(exc, 'message', str(exc))},
                status=getattr(exc, 'status', status.HTTP_400_BAD_REQUEST),
            )

        return Response({'answer_html': result['answer'], 'mock': result['mock']})


# ══════════════════════════ Dashboard ══════════════════════════


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsApproved])
def dashboard(request):
    """Bosh sahifadagi raqamlar."""
    total = Lesson.objects.count()
    completed = UserProgress.objects.filter(user=request.user, is_completed=True).count()
    results = QuizResult.objects.filter(user=request.user)

    return Response({
        'lessons': {
            'total': total,
            'completed': completed,
            'percent': round(completed * 100 / total) if total else 0,
        },
        'quizzes': {
            'taken': results.count(),
            'average_score': round(
                sum(r.score_percentage for r in results) / results.count()
            ) if results.exists() else 0,
        },
        'certificates': Certificate.objects.filter(
            user=request.user, revoked_at__isnull=True
        ).count(),
        'level': _profile(request.user).level,
    })
