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
import os

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count, Prefetch
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing import payment_requests as pr
from billing import services, telegram
from billing.dates import ALLOWED_MONTHS, format_money
from billing.gating import can_access_lesson, can_access_quiz
from core import ai_mentor, lockout, quiz_scoring, study_time
from core import password_reset as pwreset
from core.approval import is_approved
from core.models import (
    Category,
    Certificate,
    Challenge,
    Lesson,
    MentorMessage,
    ParentLink,
    Profile,
    Project,
    Quiz,
    QuizResult,
    UserProgress,
)

from .permissions import IsApproved
from .serializers import (
    CategorySerializer,
    ChallengeDetailSerializer,
    ChallengeListSerializer,
    CertificateSerializer,
    LessonDetailSerializer,
    LessonListSerializer,
    LockedLessonSerializer,
    LoginSerializer,
    MentorAskSerializer,
    MentorMessageSerializer,
    PlanOptionSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    ProjectSerializer,
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
        newly_completed = created
        if not created and not progress.is_completed:
            progress.is_completed = True
            progress.save(update_fields=['is_completed'])
            newly_completed = True

        # Kunlik hisobga FAQAT BIRINCHI MARTA qo'shiladi — bir darsni
        # qayta-qayta bosib raqamni to'ldirib bo'lmasin.
        if newly_completed:
            study_time.record_lesson_completed(request.user)

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


# ══════════════════════════ Loyihalar ══════════════════════════


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsApproved])
def projects(request):
    """Portfolio uchun loyiha g'oyalari."""
    return Response(
        ProjectSerializer(Project.objects.order_by('order'), many=True).data
    )


# ══════════════════════════ Kod muharriri ══════════════════════════


class ChallengeListView(APIView):
    """
    Topshiriqlar ro'yxati.

    `?language=python` bilan filtrlanadi. Yechim bu yerda YO'Q —
    `ChallengeListSerializer` uni umuman bermaydi.
    """

    permission_classes = [IsAuthenticated, IsApproved]

    def get(self, request):
        qs = Challenge.objects.all().order_by('order')

        language = request.query_params.get('language')
        if language:
            qs = qs.filter(language=language)

        return Response(ChallengeListSerializer(qs, many=True).data)


class ChallengeDetailView(APIView):
    permission_classes = [IsAuthenticated, IsApproved]

    def get(self, request, pk):
        challenge = get_object_or_404(Challenge, pk=pk)
        data = ChallengeDetailSerializer(challenge).data

        # Keyingi topshiriq — frontend "keyingisi" tugmasini
        # ko'rsatishi uchun
        nxt = Challenge.objects.filter(order__gt=challenge.order).order_by('order').first()
        data['next_id'] = nxt.id if nxt else None
        return Response(data)


class ChallengeSolutionView(APIView):
    """
    Yechim.

    ALOHIDA ENDPOINT: o'quvchi ATAYLAB so'raganda beriladi. Topshiriq
    ma'lumotiga qo'shilsa, u sahifa ochilishidayoq javobga tushib
    qolardi va topshiriqni yechishning ma'nosi qolmasdi.
    """

    permission_classes = [IsAuthenticated, IsApproved]

    def get(self, request, pk):
        challenge = get_object_or_404(Challenge, pk=pk)
        return Response({'solution': challenge.solution_code or ''})


# ══════════════════════════ Profil ══════════════════════════


class ProfileView(APIView):
    """Profilni o'qish va tahrirlash."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            ProfileSerializer(_profile(request.user), context={'request': request}).data
        )

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            _profile(request.user), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            ProfileSerializer(_profile(request.user), context={'request': request}).data
        )


class ProfileAvatarView(APIView):
    """
    Profil rasmini yuklash.

    ALOHIDA ENDPOINT: fayl JSON bilan bir so'rovda ketmaydi, u
    `multipart/form-data` talab qiladi.

    HAJM VA TUR TEKSHIRILADI — shablonli sahifadagi bilan bir xil
    chegaralar. Tekshiruvsiz kimdir 500 MB fayl yuborib diskni
    to'ldirib qo'yishi mumkin edi.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    MAX_SIZE = 3 * 1024 * 1024  # 3 MB
    ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')

    def post(self, request):
        image = request.FILES.get('image')
        if not image:
            return Response({'detail': 'Rasm yuborilmadi.'}, status=status.HTTP_400_BAD_REQUEST)

        if image.size > self.MAX_SIZE:
            return Response(
                {'detail': "Rasm hajmi 3 MB dan oshmasin."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        extension = os.path.splitext(image.name)[1].lower()
        if extension not in self.ALLOWED_EXTENSIONS:
            return Response(
                {'detail': "Faqat JPG, PNG yoki WEBP rasm yuklang."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = _profile(request.user)
        profile.image = image
        profile.save(update_fields=['image'])

        return Response(ProfileSerializer(profile, context={'request': request}).data)


class TelegramLinkView(APIView):
    """
    Telegram hisobini ulash uchun BIR MARTALIK havola.

    Kodning o'zi bazada saqlanmaydi — faqat SHA-256 xeshi. Havola
    Telegram tarixida qolib ketadi, baza esa tayyor kalitlar
    ro'yxatiga aylanmasligi kerak.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not telegram.is_configured():
            return Response(
                {'detail': "Telegram bot sozlanmagan."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({'url': telegram.create_link_token(request.user)})

    def delete(self, request):
        profile = _profile(request.user)
        profile.telegram_chat_id = ''
        profile.save(update_fields=['telegram_chat_id'])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ══════════════════════════ AI Mentor tarixi ══════════════════════════


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsApproved])
def mentor_history(request):
    """
    Oxirgi savol-javoblar.

    FAQAT O'ZINIKI: `filter(user=request.user)` — boshqa o'quvchining
    suhbatini ko'rish imkoni bo'lmasligi kerak.
    """
    messages_qs = (
        MentorMessage.objects.filter(user=request.user)
        .select_related('lesson')
        .order_by('-created_at')[:20]
    )
    return Response(MentorMessageSerializer(messages_qs, many=True).data)


# ══════════════════════════ O'quv vaqti ══════════════════════════


class StudyPingView(APIView):
    """
    "Men shu yerdaman" signali.

    Frontend ochiq sahifada har daqiqada bir marta yuboradi. Sana va
    qo'shiladigan miqdor SERVERDA belgilanadi — klientdan olinsa,
    bitta so'rov bilan istalgancha vaqt yozib olish mumkin bo'lardi.
    """

    permission_classes = [IsAuthenticated, IsApproved]

    def post(self, request):
        return Response(study_time.record_ping(request.user))


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsApproved])
def my_study_time(request):
    """O'quvchining o'z vaqti — dashboardda ko'rsatiladi."""
    return Response({
        'summary': study_time.summary(request.user),
        'series': study_time.daily_series(request.user, days=14),
    })


# ══════════════════════════ Ota-ona paneli ══════════════════════════


class ParentChildrenView(APIView):
    """
    Ota-onaga biriktirilgan farzandlar.

    BOG'LANISHNI FAQAT ADMIN YARATADI. Ota-ona o'zini o'zi biror
    o'quvchiga bog'lay olmaydi — aks holda har kim istagan bolaning
    natijalarini ko'rib olardi.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        links = (
            ParentLink.objects.filter(parent=request.user)
            .select_related('student__profile')
            .order_by('student__username')
        )
        return Response([
            {
                'student_id': link.student_id,
                'username': link.student.username,
                'full_name': link.student.profile.full_name or link.student.username,
                'relation': link.relation,
            }
            for link in links
        ])


class ParentChildReportView(APIView):
    """
    Bitta farzandning hisoboti.

    HUQUQ HAR SO'ROVDA TEKSHIRILADI: `ParentLink` bo'lmasa 403.
    Ro'yxatdan olingan id ni o'zgartirib boshqa bolaning hisobotini
    ko'rish imkoni bo'lmasligi kerak.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        link = (
            ParentLink.objects.filter(parent=request.user, student_id=student_id)
            .select_related('student__profile')
            .first()
        )
        if link is None:
            return Response(
                {'detail': "Bu o'quvchining hisobotini ko'rish huquqingiz yo'q."},
                status=status.HTTP_403_FORBIDDEN,
            )

        student = link.student

        results = (
            QuizResult.objects.filter(user=student)
            .select_related('quiz__lesson__module__category')
            .order_by('-completed_at')[:20]
        )

        total_lessons = Lesson.objects.count()
        completed = UserProgress.objects.filter(user=student, is_completed=True).count()

        # Bitta so'rovda: nechta test topshirgan va o'rtacha ball qancha.
        # Ilgari bu yerda to'rtta alohida so'rov bor edi.
        quiz_stats = QuizResult.objects.filter(user=student).aggregate(
            taken=Count('id'), average=Avg('score_percentage')
        )

        return Response({
            'student': {
                'id': student.id,
                'username': student.username,
                'full_name': student.profile.full_name or student.username,
                'relation': link.relation,
                'level': student.profile.level,
            },
            'study': {
                'summary': study_time.summary(student),
                'series': study_time.daily_series(student, days=14),
            },
            'lessons': {
                'total': total_lessons,
                'completed': completed,
                'percent': round(completed * 100 / total_lessons) if total_lessons else 0,
            },
            'quizzes': {
                'taken': quiz_stats['taken'],
                'average_score': round(quiz_stats['average'] or 0),
                'recent': [
                    {
                        'quiz': r.quiz.title,
                        'category': r.quiz.lesson.module.category.name,
                        'score': r.score_percentage,
                        'correct': r.correct_count,
                        'total': r.total_questions,
                        'attempts': r.attempts,
                        'completed_at': r.completed_at,
                    }
                    for r in results
                ],
            },
            'certificates': CertificateSerializer(
                Certificate.objects.filter(user=student, revoked_at__isnull=True)
                .order_by('-issued_at'),
                many=True,
                context={'request': request},
            ).data,
            'subscription': SubscriptionStateSerializer(services.get_state(student)).data,
        })
