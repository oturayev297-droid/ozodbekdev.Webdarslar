import json
import logging
import mimetypes
import os
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from urllib.parse import quote

from billing import telegram
from billing.gating import can_access_lesson, can_access_quiz, paywall
from billing.services import get_state

from . import ai_mentor, certificates, lockout, quiz_scoring, richtext, video_storage
from .approval import approval_required, is_approved
from . import password_reset as pwreset
from .models import (
    Category,
    Certificate,
    Challenge,
    Choice,
    Lesson,
    Profile,
    Project,
    Quiz,
    QuizResult,
    UserProgress,
)

logger = logging.getLogger(__name__)


# ==========================================================================
# Ochiq sahifalar
# ==========================================================================

def landing(request):
    return render(request, 'landing.html')


# ==========================================================================
# Darslar
# ==========================================================================

@approval_required
@login_required
def lessons(request, lesson_id=None):
    """Darslar sahifasi. Kontent faqat tizimga kirganlar uchun."""
    course_data = {}

    category_colors = {
        'python': 'blue',
        'django': 'green',
        'react': 'indigo',
        'javascript': 'yellow',
    }

    # Bitta so'rovda foydalanuvchining tugatgan darslari (N+1 muammosi hal qilindi)
    completed_ids = set(
        UserProgress.objects.filter(user=request.user, is_completed=True)
        .values_list('lesson_id', flat=True)
    )

    # Obuna holati BIR MARTA o'qiladi va 73 dars uchun qayta-qayta
    # so'ralmaydi.
    subscribed = get_state(request.user).active

    categories = Category.objects.all().prefetch_related(
        'modules__lessons',
        # Rasmlarsiz har bir dars uchun alohida so'rov ketardi:
        # 73 dars = 73 ta qo'shimcha so'rov.
        'modules__lessons__images',
    )

    for category in categories:
        cat_slug = category.slug.lower()
        lessons_list = []

        all_lessons = []
        for module in category.modules.all().order_by('order'):
            all_lessons.extend(module.lessons.all().order_by('order'))

        completed_count = 0
        free_count = 0
        for lesson in all_lessons:
            is_completed = lesson.id in completed_ids
            if is_completed:
                completed_count += 1
            if lesson.is_free:
                free_count += 1

            unlocked = lesson.is_free or subscribed

            # QULFLANGAN DARSNING MAZMUNI UMUMAN YUBORILMAYDI.
            # Sarlavha qoladi — o'quvchi nima sotib olayotganini ko'rsin —
            # lekin nazariya, kod va video havolasi JSON ga tushmaydi.
            # Faqat CSS bilan yashirish yetarli emas: sahifa manbasidan
            # o'qib olinardi.
            if unlocked:
                if lesson.video_file:
                    video_url = f'/lessons/{lesson.id}/video/'
                else:
                    video_url = lesson.video_url or ''
                # Tavsif bezak belgilaridan tozalanadi — kartochkada
                # "## Sarlavha" ko'rinib qolmasin
                description = richtext.plain_summary(lesson.theory) or "Tavsif yo'q"
                code = lesson.practice_code
                # HTML SERVERDA quriladi: matn to'liq ekranlanadi va
                # faqat ruxsat etilgan teglar qo'yiladi, shuning uchun
                # uni brauzerda innerHTML ga berish xavfsiz.
                theory_html = richtext.render(lesson.theory)
                images = [
                    {
                        'url': img.image.url,
                        'caption': img.caption,
                        'alt': img.display_alt,
                    }
                    for img in lesson.images.all()
                    if img.image
                ]
            else:
                video_url = ''
                description = "Bu dars obuna bilan ochiladi."
                code = ''
                theory_html = ''
                # RASMLAR HAM YUBORILMAYDI: dars matni rasmda bo'lsa,
                # ularni qoldirish qulfni ma'nosiz qilardi.
                images = []

            lessons_list.append({
                'id': lesson.id,
                'title': lesson.title,
                'description': description,
                'videoUrl': video_url,
                'code': code,
                'theoryHtml': theory_html,
                'images': images,
                'hasText': bool(theory_html),
                'completed': is_completed,
                'isFree': lesson.is_free,
                'unlocked': unlocked,
            })

        course_data[cat_slug] = {
            'name': category.name,
            # Kurs kartochkasidagi tavsif. Bo'lim tavsifi bo'sh bo'lsa
            # kartochkada shunchaki matn chiqmaydi — bu sahifani
            # buzmaydi.
            'description': category.description or '',
            'color': category_colors.get(cat_slug, 'blue'),
            'totalLessons': len(all_lessons),
            'completedLessons': completed_count,
            'freeLessons': free_count,
            'lessons': lessons_list,
        }

    context = {
        'course_data_json': json.dumps(course_data, cls=DjangoJSONEncoder),
        'initial_lesson_id': lesson_id or '',
        'subscribed': subscribed,
    }
    return render(request, 'lessons.html', context)


@approval_required
@login_required
def lesson_video(request, lesson_id):
    """
    Dars videosini FAQAT huquqi bor foydalanuvchiga uzatadi.

    UCHTA REJIM, sozlamaga qarab tanlanadi:

      1. Bulut (S3/R2) -> imzolangan vaqtinchalik havolaga yo'naltiradi
      2. nginx         -> X-Accel-Redirect, faylni nginx uzatadi
      3. Django        -> faylni o'zi uzatadi (FAQAT lokal)

    Uchalasida ham HUQUQ SHU YERDA, Django tomonida tekshiriladi.
    Havola faqat tekshiruvdan keyin beriladi.

    3-rejim productionda ishlatilmaydi: 5 GB faylni uzatayotgan
    Django worker'i butun video davomida band bo'lib qoladi.
    """
    from django.conf import settings

    lesson = get_object_or_404(Lesson, id=lesson_id)

    # DARVOZA: bepul dars hammaga, qolgani faol obunaga.
    if not can_access_lesson(request.user, lesson):
        return paywall(request, "Bu dars videosi obuna bilan ochiladi.")

    if not lesson.video_file:
        raise Http404("Bu darsda video yo'q")

    name = lesson.video_file.name

    # ── 1. Bulut ombori ──
    if video_storage.is_cloud_enabled():
        try:
            url = video_storage.signed_url(name)
        except video_storage.VideoStorageError:
            logger.exception("Imzolangan havola olinmadi: %s", name)
            raise Http404("Video hozircha mavjud emas")
        # 302: brauzer to'g'ridan-to'g'ri omborga boradi va Django
        # trafikda umuman qatnashmaydi.
        return redirect(url)

    # ── 2. nginx ──
    if settings.USE_X_ACCEL_REDIRECT:
        response = HttpResponse()
        # nginx da: location /protected/ { internal; alias /path/to/media/; }
        response['X-Accel-Redirect'] = f'/protected/{name}'
        response['Content-Type'] = (
            mimetypes.guess_type(name)[0] or 'application/octet-stream'
        )
        del response['Content-Length']
        return response

    # ── 3. Django (faqat lokal) ──
    try:
        return FileResponse(lesson.video_file.open('rb'), content_type='video/mp4')
    except FileNotFoundError:
        logger.error("Video fayl diskda topilmadi: %s", name)
        raise Http404("Video fayl topilmadi")


@approval_required
@login_required
@require_POST
def complete_lesson(request, lesson_id):
    """Darsni 'tugatildi' deb belgilaydi. Dashboard statistikasi shundan oziqlanadi."""
    lesson = get_object_or_404(Lesson, id=lesson_id)

    # Ko'ra olmagan darsni tugatilgan deb belgilab bo'lmaydi — aks holda
    # obunasiz odam o'zlashtirish foizini to'ldirib chiqardi.
    if not can_access_lesson(request.user, lesson):
        return paywall(request, "Bu dars obuna bilan ochiladi.")

    progress, created = UserProgress.objects.get_or_create(
        user=request.user,
        lesson=lesson,
        defaults={'is_completed': True, 'completed_at': timezone.now()},
    )
    if not created and not progress.is_completed:
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.save(update_fields=['is_completed', 'completed_at'])

    total_completed = UserProgress.objects.filter(
        user=request.user, is_completed=True
    ).count()

    return JsonResponse({
        'success': True,
        'lesson_id': lesson.id,
        'completed': True,
        'total_completed': total_completed,
    })


# ==========================================================================
# Dashboard
# ==========================================================================

@approval_required
@login_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    tech_progress = {'python': 0, 'django': 0, 'javascript': 0, 'react': 0}

    latest_quizzes = (
        QuizResult.objects.filter(user=request.user)
        .select_related('quiz')
        .order_by('-completed_at')[:5]
    )

    completed_lessons_count = UserProgress.objects.filter(
        user=request.user, is_completed=True
    ).count()
    # Haqiqiy berilgan sertifikatlar. Ilgari bu QuizResult dan har safar
    # qayta hisoblanardi — natija keyin o'zgarsa raqam ham o'zgarib ketardi.
    certificates_count = Certificate.objects.filter(
        user=request.user, revoked_at__isnull=True
    ).count()

    total_quiz_score = sum(
        r.score_percentage for r in QuizResult.objects.filter(user=request.user)
    )
    code_points = (profile.level * 150) + (completed_lessons_count * 25) + total_quiz_score

    for category in Category.objects.all():
        slug = category.slug.lower()
        if slug not in tech_progress and slug != 'nodejs':
            continue
        mapped_slug = 'javascript' if slug == 'nodejs' else slug

        total_lessons = Lesson.objects.filter(module__category=category).count()
        total_quizzes = Quiz.objects.filter(lesson__module__category=category).count()

        completed_lessons = UserProgress.objects.filter(
            user=request.user,
            lesson__module__category=category,
            is_completed=True,
        ).count()
        completed_quizzes = QuizResult.objects.filter(
            user=request.user,
            quiz__lesson__module__category=category,
            score_percentage__gte=50,
        ).count()

        combined_total = total_lessons + total_quizzes
        if combined_total > 0:
            combined_completed = completed_lessons + completed_quizzes
            tech_progress[mapped_slug] = int((combined_completed / combined_total) * 100)

    # Haftalik faollik (endi Asia/Tashkent vaqt zonasida)
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    current_week_activity = []
    current_week_total = 0
    previous_week_total = 0

    for i in range(6, -1, -1):
        day_start = today - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        d_q = QuizResult.objects.filter(
            user=request.user, completed_at__gte=day_start, completed_at__lt=day_end
        ).count()
        d_l = UserProgress.objects.filter(
            user=request.user,
            completed_at__gte=day_start,
            completed_at__lt=day_end,
            is_completed=True,
        ).count()
        total = d_q + d_l
        current_week_activity.append(total)
        current_week_total += total

    for i in range(13, 6, -1):
        day_start = today - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        d_q = QuizResult.objects.filter(
            user=request.user, completed_at__gte=day_start, completed_at__lt=day_end
        ).count()
        d_l = UserProgress.objects.filter(
            user=request.user,
            completed_at__gte=day_start,
            completed_at__lt=day_end,
            is_completed=True,
        ).count()
        previous_week_total += (d_q + d_l)

    if previous_week_total > 0:
        activity_growth = int(
            ((current_week_total - previous_week_total) / previous_week_total) * 100
        )
    elif current_week_total > 0:
        activity_growth = 100
    else:
        activity_growth = 0

    max_act = max(current_week_activity) or 1
    activity_bars = [
        max(15, int((val / max_act) * 100)) if val > 0 else 5
        for val in current_week_activity
    ]

    latest_lesson = Lesson.objects.order_by('-created_at').first()

    return render(request, 'dashboard.html', {
        'profile': profile,
        'latest_lesson': latest_lesson,
        'latest_quizzes': latest_quizzes,
        'tech_progress': tech_progress,
        'completed_lessons_count': completed_lessons_count,
        'certificates_count': certificates_count,
        'code_points': code_points,
        'activity_bars': activity_bars,
        'activity_growth': activity_growth,
    })


# ==========================================================================
# Kod muharriri va loyihalar
# ==========================================================================

@approval_required
@login_required
def editor(request, challenge_id=None):
    challenges = Challenge.objects.all().order_by('order')
    current_challenge = None
    if challenge_id:
        current_challenge = get_object_or_404(Challenge, id=challenge_id)
    elif challenges.exists():
        current_challenge = challenges.first()

    context = {
        'challenges': challenges,
        'current_challenge': current_challenge,
        # Tavsif endi ODDIY MATN (HTML dan `convert_challenge_html`
        # bilan o'tkazilgan) va u `richtext` orqali chiqariladi —
        # dars matni bilan bir xil yo'l.
        'description_html': (
            richtext.render(current_challenge.description) if current_challenge else ''
        ),
        'next_challenge': (
            challenges.filter(order__gt=current_challenge.order).first()
            if current_challenge else None
        ),
    }
    return render(request, 'editor.html', context)


@approval_required
@login_required
def challenge_solution(request, challenge_id):
    """Yechimni faqat so'ralganda beradi — HTML manbasida ochiq turmaydi."""
    challenge = get_object_or_404(Challenge, id=challenge_id)
    return JsonResponse({'solution': challenge.solution_code or ''})


@approval_required
@login_required
def projects(request):
    projects_list = Project.objects.all().order_by('order')
    for project in projects_list:
        project.tech_list = [
            t.strip() for t in (project.tech_stack or '').split(',') if t.strip()
        ]
    return render(request, 'projects.html', {'projects': projects_list})


# ==========================================================================
# Testlar
# ==========================================================================

def _visible_quizzes(user):
    """
    O'quvchi ko'ra oladigan testlar.

    Qoralama (nashr qilinmagan) testlar YASHIRILADI — `generate_quizzes`
    yozgan savol tekshirilmaguncha o'quvchiga ko'rinmasligi kerak.
    Xodimlar ko'radi, chunki ular aynan tekshirish uchun ochadi.
    """
    qs = Quiz.objects.select_related('lesson__module__category')
    if user.is_staff:
        return qs
    return qs.filter(is_published=True)


@approval_required
@login_required
def quizzes(request):
    quiz_list = _visible_quizzes(request.user)

    # Test darsdan huquqni meros oladi — o'z bayrog'i yo'q.
    subscribed = get_state(request.user).active
    for quiz in quiz_list:
        quiz.unlocked = quiz.lesson.is_free or subscribed

    return render(request, 'quizzes.html', {
        'quizzes': quiz_list,
        'categories': Category.objects.all(),
        'subscribed': subscribed,
    })


@approval_required
@login_required
def quiz_detail(request, quiz_id):
    quiz = get_object_or_404(_visible_quizzes(request.user), id=quiz_id)

    if not can_access_quiz(request.user, quiz):
        return paywall(request, "Bu test obuna bilan ochiladi.")

    questions = quiz.questions.all().prefetch_related('choices')
    return render(request, 'quiz_detail.html', {
        'quiz': quiz,
        'questions': questions,
    })


@approval_required
@login_required
@require_POST
def submit_quiz(request, quiz_id):
    """
    Ballni SERVER hisoblaydi.

    Klient faqat {"answers": {"<question_id>": <choice_id>, ...}} yuboradi.
    To'g'ri javoblar HTML ga umuman chiqmaydi, shuning uchun natijani
    soxtalashtirib bo'lmaydi.
    """
    quiz = get_object_or_404(_visible_quizzes(request.user), id=quiz_id)

    if not can_access_quiz(request.user, quiz):
        return paywall(request, "Bu test obuna bilan ochiladi.")

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Noto\'g\'ri format'}, status=400)

    answers = payload.get('answers') or {}
    if not isinstance(answers, dict):
        return JsonResponse({'success': False, 'error': 'Noto\'g\'ri javoblar'}, status=400)

    # BALL SHU YERDA HISOBLANMAYDI — `core.quiz_scoring` da.
    # API ham aynan o'sha funksiyani chaqiradi, shuning uchun ikki
    # joyda ikki xil ball chiqishi mumkin emas.
    try:
        outcome = quiz_scoring.score_quiz(request.user, quiz, answers)
    except quiz_scoring.ScoringError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)

    certificate = outcome['certificate']
    return JsonResponse({
        'success': True,
        'score': outcome['score'],
        'correct': outcome['correct'],
        'total': outcome['total'],
        'new_level': outcome['new_level'],
        'leveled_up': outcome['leveled_up'],
        'certificate_url': (
            reverse('certificate_pdf', args=[certificate.code]) if certificate else None
        ),
    })


# ==========================================================================
# Autentifikatsiya
# ==========================================================================

def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        email = (request.POST.get('email') or '').strip().lower()
        password = request.POST.get('password') or ''
        password2 = request.POST.get('password2') or ''
        full_name = (request.POST.get('full_name') or '').strip()

        form_data = {'username': username, 'email': email, 'full_name': full_name}

        if not username or not password:
            messages.error(request, 'Foydalanuvchi nomi va parol majburiy.')
            return render(request, 'register.html', form_data)

        # Email endi MAJBURIY: parolni tiklash faqat shu orqali ishlaydi.
        # Emailsiz hisob parolini unutsa, uni qaytarib bo'lmasdi.
        if not email:
            messages.error(request, 'Email majburiy — parolni tiklash uchun kerak.')
            return render(request, 'register.html', form_data)

        if len(username) < 3:
            messages.error(request, 'Foydalanuvchi nomi kamida 3 ta belgidan iborat bo\'lsin.')
            return render(request, 'register.html', form_data)

        if password2 and password != password2:
            messages.error(request, 'Parollar mos kelmadi.')
            return render(request, 'register.html', form_data)

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, 'Ushbu foydalanuvchi nomi band.')
            return render(request, 'register.html', form_data)

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'Bu email allaqachon ro\'yxatdan o\'tgan.')
            return render(request, 'register.html', form_data)

        try:
            validate_password(password)
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
            return render(request, 'register.html', form_data)

        user = User.objects.create_user(username=username, email=email, password=password)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.full_name = full_name
        profile.save(update_fields=['full_name'])

        login(request, user)
        logger.info("Yangi ro'yxatdan o'tish: %s (ruxsat kutilmoqda)", username)

        # Adminga darhol xabar beramiz. Xabar ketmasa ham ro'yxatdan
        # o'tish BUZILMAYDI — Telegram sozlanmagan bo'lishi mumkin, va
        # bu o'quvchining muammosi emas.
        try:
            telegram.notify_new_registration(user)
        except Exception:
            logger.exception("Yangi ro'yxatdan o'tish haqida xabar yuborilmadi")

        # Dashboard EMAS: yangi hisob ruxsat kutadi va u yerda
        # baribir kutish sahifasiga qaytarilardi.
        return redirect('pending_approval')

    return render(request, 'register.html')


@login_required
def pending_approval(request):
    """
    Ruxsat kutayotgan o'quvchi sahifasi.

    Ruxsati BOR odam bu yerga tushsa dashboardga qaytariladi — aks
    holda ruxsat berilgandan keyin ham eski havola bo'yicha kutish
    sahifasini ko'rib, hech narsa o'zgarmagandek tuyulardi.
    """
    if is_approved(request.user):
        return redirect('dashboard')

    profile = getattr(request.user, 'profile', None)
    return render(request, 'pending_approval.html', {
        'profile': profile,
        'rejected': bool(profile and profile.rejection_reason),
    })


def user_login(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('/admin/')
        return redirect('dashboard')

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        ip = lockout.client_ip(request)

        # DARVOZA: parolni tekshirishdan OLDIN. Qulflangan bo'lsa urinish
        # yozilmaydi ham — aks holda hujumchi urinib turib qulfni cheksiz
        # uzaytirardi va haqiqiy egasi hech qachon kira olmasdi.
        locked, retry_after, _ = lockout.check_locked(username, ip)
        if locked:
            messages.error(request, lockout.lockout_message(retry_after))
            return render(request, 'login.html', {'locked': True}, status=429)

        user = authenticate(request, username=username, password=password)
        if user is not None:
            lockout.record_success(request, user)
            login(request, user)
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            if user.is_staff:
                return redirect('/admin/')
            return redirect('dashboard')

        lockout.record_failure(request, username)

        # Oxirgi urinish chegaraga yetgan bo'lsa darhol xabar beramiz —
        # foydalanuvchi nima bo'lganini tushunsin
        locked, retry_after, _ = lockout.check_locked(username, ip)
        if locked:
            messages.error(request, lockout.lockout_message(retry_after))
            return render(request, 'login.html', {'locked': True}, status=429)

        messages.error(request, 'Login yoki parol noto\'g\'ri.')

    return render(request, 'login.html')


@require_POST
def user_logout(request):
    logout(request)
    return redirect('landing')


# ==========================================================================
# AI Mentor
# ==========================================================================


@approval_required
@login_required
@require_POST
def mentor_ask(request):
    """
    AI Mentor'ga savol.

    Suhbat tarixi SERVERDA saqlanadi — klientdan qabul qilinmaydi.
    Aks holda o'quvchi soxta "assistant" javoblarini yuborib modelni
    boshqarib olardi.
    """
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': "Noto'g'ri format"}, status=400)

    # Dars konteksti — faqat o'quvchi ko'ra oladigan dars qabul qilinadi
    lesson = None
    lesson_id = payload.get('lesson_id')
    if lesson_id:
        lesson = Lesson.objects.filter(id=lesson_id).select_related(
            'module__category'
        ).first()
        if lesson and not can_access_lesson(request.user, lesson):
            lesson = None

    try:
        result = ai_mentor.ask(request.user, payload.get('question'), lesson=lesson)
    except ai_mentor.MentorError as exc:
        return JsonResponse({'success': False, 'error': exc.message}, status=exc.status)

    return JsonResponse({
        'success': True,
        'answer': result['answer'],
        'mock': result['mock'],
    })


# ==========================================================================
# Sertifikatlar
# ==========================================================================


@approval_required
@login_required
def my_certificates(request):
    """O'quvchining sertifikatlari."""
    items = (
        Certificate.objects.filter(user=request.user)
        .select_related('quiz')
        .order_by('-issued_at')
    )
    return render(request, 'certificates.html', {
        'certificates': items,
        'pass_score': certificates.PASS_SCORE,
    })


@approval_required
@login_required
def certificate_pdf(request, code):
    """
    Sertifikat PDF si.

    Faqat EGASI yoki admin yuklab oladi. Ommaviy tekshirish uchun
    alohida sahifa bor (`verify_certificate`) — u PDF bermaydi, chunki
    kodni bilgan har kim boshqaning hujjatini yuklab olmasligi kerak.
    """
    certificate = get_object_or_404(
        Certificate.objects.select_related('quiz', 'user'), code=code
    )
    if certificate.user_id != request.user.id and not request.user.is_staff:
        raise Http404("Sertifikat topilmadi")

    verify_url = request.build_absolute_uri(
        reverse('verify_certificate') + f'?code={certificate.code}'
    )
    pdf = certificates.build_pdf(certificate, verify_url=verify_url)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="{certificates.filename_for(certificate)}"'
    )
    return response


def verify_certificate(request):
    """
    Sertifikatni tekshirish — OMMAVIY sahifa, login talab qilmaydi.

    Ish beruvchi kodni kiritib hujjat haqiqiyligini ko'radi. Faqat
    tasdiqlash uchun zarur ma'lumot ko'rsatiladi: ism, kurs, ball, sana
    va amaldaligi. Email, foydalanuvchi nomi va boshqa shaxsiy
    ma'lumotlar chiqarilmaydi.
    """
    code = (request.GET.get('code') or '').strip().upper()
    certificate = None
    searched = bool(code)

    if searched:
        certificate = (
            Certificate.objects.select_related('quiz')
            .filter(code=code)
            .first()
        )
        if certificate is None:
            logger.info("[SERTIFIKAT] Tekshirish: kod topilmadi (%s)", code[:40])

    return render(request, 'verify_certificate.html', {
        'code': code,
        'certificate': certificate,
        'searched': searched,
    })


# ==========================================================================
# Parolni tiklash
# ==========================================================================


def forgot_password(request):
    """1-qadam: emailga 6 xonali kod yuboriladi."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '')
        ip = lockout.client_ip(request)

        # Cheklovsiz bu begonaning pochtasiga xat yuborish vositasi bo'lardi
        throttled, retry_after = lockout.check_reset_throttle(ip)
        if throttled:
            messages.error(request, lockout.reset_throttle_message(retry_after))
            return render(request, 'forgot_password.html', status=429)

        lockout.record_reset_request(request, email)

        # Javob email bor-yo'qligidan qat'i nazar bir xil
        message = pwreset.request_reset(email)
        messages.success(request, message)
        return redirect(f"{reverse('reset_password')}?email={quote(email.strip().lower())}")

    return render(request, 'forgot_password.html')


def reset_password(request):
    """2-qadam: kod va yangi parol."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    email = (request.GET.get('email') or request.POST.get('email') or '').strip()

    if request.method == 'POST':
        code = request.POST.get('code', '')
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        if password != password2:
            messages.error(request, 'Parollar mos kelmadi.')
            return render(request, 'reset_password.html', {'email': email})

        try:
            message = pwreset.confirm_reset(email, code, password)
        except pwreset.ResetError as exc:
            messages.error(request, exc.message)
            return render(request, 'reset_password.html', {'email': email})

        messages.success(request, message)
        return redirect('login')

    return render(request, 'reset_password.html', {'email': email})


@login_required
def profile(request):
    user_profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        image = request.FILES.get('image')
        if image:
            if image.size > 3 * 1024 * 1024:
                messages.error(request, 'Rasm hajmi 3 MB dan oshmasin.')
                return render(request, 'profile.html', {'profile': user_profile})
            ext = os.path.splitext(image.name)[1].lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
                messages.error(request, 'Faqat JPG, PNG yoki WEBP rasm yuklang.')
                return render(request, 'profile.html', {'profile': user_profile})
            user_profile.image = image

        user_profile.full_name = request.POST.get('full_name', user_profile.full_name)
        user_profile.bio = request.POST.get('bio', user_profile.bio)
        user_profile.save()
        messages.success(request, 'Profil yangilandi.')
        return redirect('dashboard')

    return render(request, 'profile.html', {'profile': user_profile})
