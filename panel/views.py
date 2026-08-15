"""
Panel sahifalari
================

QOIDALAR:

1. PANEL BIZNES MANTIQNI TAKRORLAMAYDI. To'lovni tasdiqlash, obunani
   uzaytirish, sinov berish — hammasi `billing.payment_requests` va
   `billing.services` orqali. Panel bu funksiyalarni CHAQIRADI, o'z
   nusxasini yozmaydi. Aks holda ikki joyda ikki xil qoida paydo
   bo'lardi va qaysi biri to'g'ri ekani bilinmasdi.

2. `current_period_end` ni panel HECH QACHON to'g'ridan-to'g'ri
   o'zgartirmaydi. Yagona yo'l — `services.extend_subscription`.

3. HAR BIR O'ZGARTIRUVCHI AMAL POST. GET faqat ko'rsatadi. Aks holda
   havolani bosish yoki sahifani yangilash pul harakatini takrorlardi.

4. Ro'yxatlarda `select_related` majburiy: 100 qatorli jadval 300 ta
   so'rovga aylanib ketmasin.
"""

import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, Prefetch, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from billing import payment_requests as pr
from billing import telegram
from billing import services
from billing.dates import format_money, now as billing_now
from billing.models import (
    OPEN_STATUSES,
    GatewayTransaction,
    PaymentRequest,
    PeriodSource,
    RequestStatus,
    Subscription,
    SubscriptionPeriod,
)
from core import approval
from core.models import (
    Category,
    Certificate,
    Lesson,
    LessonImage,
    LoginAttempt,
    MentorMessage,
    Module,
    Quiz,
)

from . import messaging, reports
from .auth import staff_required
from .forms import LessonForm, LessonImageForm, ModuleForm
from .models import Audience, PanelMessage

logger = logging.getLogger(__name__)

PAGE_SIZE = 25


def _with_heights(series):
    """
    Grafik ustunlarining balandligini QO'SHADI.

    Shablonda `widthratio` bilan hisoblash mumkin edi, lekin barcha
    qiymatlar nol bo'lganda u nolga bo'lishga urinardi. Bu yerda esa
    chegara bir marta, tushunarli qilib qo'yiladi.
    """
    peak = max((row['total_tiyin'] for row in series), default=0)
    for row in series:
        row['height_percent'] = round(row['total_tiyin'] * 100 / peak, 1) if peak else 0
    return series


def _page(request, queryset, per_page=PAGE_SIZE):
    """Sahifalash. Noto'g'ri `?page=` bo'lsa birinchi sahifa ko'rsatiladi."""
    paginator = Paginator(queryset, per_page)
    try:
        number = int(request.GET.get('page', 1))
    except (TypeError, ValueError):
        number = 1
    return paginator.get_page(number)


# ─────────────────────────── Bosh sahifa ───────────────────────────


@staff_required
def dashboard(request):
    """Umumiy ko'rsatkichlar."""
    context = reports.dashboard_context()
    context['series'] = _with_heights(reports.monthly_series(months=6))

    # Eng shoshilinchi ish: pul yuborilgan, javob kutilmoqda
    context['awaiting'] = (
        PaymentRequest.objects.filter(status=RequestStatus.RECEIPT_UPLOADED)
        .select_related('user', 'plan')
        .order_by('receipt_sent_at')[:10]
    )
    context['recent_periods'] = (
        SubscriptionPeriod.objects.filter(source=PeriodSource.PAYMENT)
        .select_related('subscription__user', 'plan')
        .order_by('-created_at')[:10]
    )
    return render(request, 'panel/dashboard.html', context)


# ─────────────────────────── Moliya ───────────────────────────


@staff_required
def finance(request):
    """Pul aylanmasi: oylar kesimi, to'lov usullari, bepul berilganlar."""
    months = 12
    try:
        months = max(3, min(24, int(request.GET.get('months', 12))))
    except (TypeError, ValueError):
        pass

    at = billing_now()
    this_month = reports.month_start(at)

    series = _with_heights(reports.monthly_series(months=months, at=at))

    return render(request, 'panel/finance.html', {
        'months': months,
        'series': series,
        'series_total': format_money(sum(r['total_tiyin'] for r in series)),
        'methods_all': reports.method_breakdown(),
        'methods_month': reports.method_breakdown(start=this_month),
        'revenue_month': reports.revenue_between(
            this_month, reports.month_start(this_month.replace(day=28) + timedelta(days=4))
        ),
        'granted': reports.granted_summary(),
        'requests': reports.pending_requests(),
        'subscribers': reports.subscriber_counts(at),
    })


@staff_required
def periods(request):
    """Obuna davrlari jurnali — o'zgartirib bo'lmaydigan moliyaviy tarix."""
    qs = SubscriptionPeriod.objects.select_related(
        'subscription__user', 'plan', 'created_by_admin'
    ).order_by('-created_at')

    source = request.GET.get('source', '')
    if source:
        qs = qs.filter(source=source)

    query = (request.GET.get('q') or '').strip()
    if query:
        qs = qs.filter(
            Q(subscription__user__username__icontains=query)
            | Q(subscription__user__email__icontains=query)
        )

    return render(request, 'panel/periods.html', {
        'page_obj': _page(request, qs),
        'source': source,
        'q': query,
        'sources': PeriodSource.choices,
    })


# ─────────────────────────── To'lov so'rovlari ───────────────────────────


@staff_required
def payments(request):
    """To'lov so'rovlari navbati."""
    status = request.GET.get('status', 'open')

    qs = PaymentRequest.objects.select_related('user', 'plan', 'reviewed_by_admin')
    if status == 'open':
        qs = qs.filter(status__in=[s.value for s in OPEN_STATUSES])
    elif status:
        qs = qs.filter(status=status)

    query = (request.GET.get('q') or '').strip()
    if query:
        qs = qs.filter(Q(user__username__icontains=query) | Q(user__email__icontains=query))

    # ENG SHOSHILINCHI TEPADA: chek yuborilgan so'rovlarda o'quvchining
    # puli allaqachon ketgan va u javob kutmoqda. Ular sana bo'yicha
    # ro'yxatning o'rtasiga tushib ketsa, e'tibordan chetda qolardi.
    qs = qs.annotate(
        urgency=Case(
            When(status=RequestStatus.RECEIPT_UPLOADED, then=Value(0)),
            When(status=RequestStatus.CARD_ISSUED, then=Value(1)),
            When(status=RequestStatus.REQUESTED, then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('urgency', '-requested_at')

    return render(request, 'panel/payments.html', {
        'page_obj': _page(request, qs),
        'status': status,
        'q': query,
        'statuses': RequestStatus.choices,
        'awaiting': PaymentRequest.objects.filter(
            status=RequestStatus.RECEIPT_UPLOADED
        ).count(),
        'methods': [
            c for c in SubscriptionPeriod._meta.get_field('payment_method').choices or []
        ],
    })


@require_POST
@staff_required
def payment_action(request, request_id):
    """
    To'lov so'roviga amal.

    HAMMASI `billing.payment_requests` orqali (1-qoida): karta berish,
    tasdiqlash, rad etish. Panel bu yerda faqat formani o'qiydi va
    natijani ko'rsatadi.
    """
    action = request.POST.get('action')
    note = (request.POST.get('note') or '').strip()

    try:
        if action == 'issue_card':
            obj = pr.issue_card(request_id, request.user)
            messages.success(request, f"#{obj.pk}: karta rekvizitlari berildi.")

        elif action == 'confirm':
            # `confirm_request` obunani uzaytiradi, jurnalga yozadi va
            # o'quvchiga Telegramda xabar beradi — hammasi o'zida.
            result = pr.confirm_request(
                request_id, request.user, payment_method=request.POST.get('payment_method') or None,
                note=note,
            )
            messages.success(
                request,
                f"#{request_id}: tasdiqlandi. "
                f"{format_money(result.period.amount_tiyin)} — "
                f"obuna {result.current_period_end:%d.%m.%Y} gacha uzaytirildi.",
            )

        elif action == 'reject':
            if not note:
                messages.error(request, "Rad etish sababi yozilishi shart.")
                return redirect(request.POST.get('back') or 'panel:payments')
            obj = pr.reject_request(request_id, request.user, note)
            messages.success(request, f"#{obj.pk}: rad etildi.")

        else:
            messages.error(request, "Noma'lum amal.")

    except services.BillingError as exc:
        messages.error(request, str(exc))

    return redirect(request.POST.get('back') or 'panel:payments')


@staff_required
def gateway_log(request):
    """Payme / Click tranzaksiyalari — tergov uchun."""
    qs = GatewayTransaction.objects.select_related('payment_request__user').order_by('-created_at')

    provider = request.GET.get('provider', '')
    if provider:
        qs = qs.filter(provider=provider)

    return render(request, 'panel/gateways.html', {
        'page_obj': _page(request, qs),
        'provider': provider,
        'providers': GatewayTransaction.Provider.choices,
    })


# ─────────────────────────── O'quvchilar ───────────────────────────


@staff_required
def students(request):
    """O'quvchilar ro'yxati va obuna holati."""
    at = billing_now()

    qs = (
        User.objects.filter(is_staff=False)
        .select_related('profile', 'subscription__plan')
        .annotate(
            completed=Count('progress', filter=Q(progress__is_completed=True), distinct=True),
            quizzes=Count('quiz_results', distinct=True),
        )
        .order_by('-date_joined')
    )

    query = (request.GET.get('q') or '').strip()
    if query:
        qs = qs.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(profile__full_name__icontains=query)
        )

    state = request.GET.get('state', '')
    if state == 'pending':
        # Ruxsat kutayotganlar — eng shoshilinch ro'yxat
        qs = qs.filter(profile__is_approved=False)
    elif state == 'active':
        qs = qs.filter(subscription__current_period_end__gt=at)
    elif state == 'expired':
        qs = qs.filter(subscription__current_period_end__lte=at)
    elif state == 'none':
        qs = qs.filter(subscription__isnull=True)
    elif state == 'telegram':
        qs = qs.filter(profile__telegram_chat_id__gt='')

    # Kutayotganlar TEPADA: yangi odam javob kutib turibdi, u sana
    # bo'yicha ro'yxatning o'rtasiga tushib ketmasligi kerak.
    if not state:
        qs = qs.order_by('profile__is_approved', '-date_joined')

    return render(request, 'panel/students.html', {
        'page_obj': _page(request, qs),
        'q': query,
        'state': state,
        'now': at,
        'counts': reports.subscriber_counts(at),
        'pending_count': User.objects.filter(
            is_staff=False, profile__is_approved=False
        ).count(),
    })


@require_POST
@staff_required
def student_approval(request, user_id):
    """
    O'quvchiga ruxsat berish yoki olib tashlash.

    RUXSAT VA OBUNA — ALOHIDA NARSA. Bu yerda faqat ruxsat
    o'zgartiriladi; obuna `billing` orqali, to'lov tasdiqlanganda
    uzayadi. Ikkalasi bir tugmaga birlashtirilsa, admin bepul
    kirish berayotganini sezmay qolardi.
    """
    student = get_object_or_404(
        User.objects.select_related('profile'), pk=user_id, is_staff=False
    )
    profile = student.profile
    action = request.POST.get('action')

    if action == 'approve':
        approval.approve(profile, admin=request.user)
        messages.success(request, f"{student.username}: ruxsat berildi.")
        try:
            telegram.notify_approved(student)
        except Exception:
            logger.exception("Ruxsat haqida xabar yuborilmadi")

    elif action == 'revoke':
        reason = (request.POST.get('reason') or '').strip()
        if not reason:
            messages.error(request, "Sabab yozilishi shart — u o'quvchiga ko'rsatiladi.")
            return redirect(request.POST.get('back') or 'panel:students')

        approval.revoke(profile, reason=reason, admin=request.user)
        messages.success(request, f"{student.username}: ruxsat olib tashlandi.")
        try:
            telegram.notify_rejected_registration(student, reason)
        except Exception:
            logger.exception("Rad etish haqida xabar yuborilmadi")

    else:
        messages.error(request, "Noma'lum amal.")

    return redirect(request.POST.get('back') or 'panel:students')


@staff_required
def student_detail(request, user_id):
    """Bitta o'quvchi: obuna, to'lovlar, natijalar."""
    student = get_object_or_404(
        User.objects.select_related('profile', 'subscription__plan'), pk=user_id, is_staff=False
    )
    state = services.get_state(student)

    return render(request, 'panel/student_detail.html', {
        'student': student,
        'state': state,
        # Holat nomi shablonda emas, shu yerda tarjima qilinadi —
        # `SubscriptionState` ning o'zida `label` yo'q.
        'state_label': services.STATUS_LABELS.get(state.status, state.status),
        'periods': SubscriptionPeriod.objects.filter(subscription__user=student)
        .select_related('plan', 'created_by_admin')
        .order_by('-created_at')[:20],
        'requests': PaymentRequest.objects.filter(user=student)
        .select_related('plan')
        .order_by('-requested_at')[:20],
        'certificates': Certificate.objects.filter(user=student).order_by('-issued_at')[:10],
        'mentor': MentorMessage.objects.filter(user=student).order_by('-created_at')[:10],
        'audiences': Audience.choices,
    })


@require_POST
@staff_required
def student_grant(request, user_id):
    """
    Bepul kun berish.

    `services.extend_subscription` orqali, `source=ADMIN_GRANT` bilan —
    demak TUSHUMGA KIRMAYDI (2-qoida va hisobot qoidalari).
    """
    student = get_object_or_404(User, pk=user_id, is_staff=False)

    try:
        days = int(request.POST.get('days', 0))
    except (TypeError, ValueError):
        days = 0

    if days < 1 or days > 365:
        messages.error(request, "Kun soni 1 dan 365 gacha bo'lishi kerak.")
        return redirect('panel:student_detail', user_id=user_id)

    try:
        services.extend_subscription(
            user=student,
            days=days,
            source=PeriodSource.ADMIN_GRANT,
            admin=request.user,
            note=(request.POST.get('note') or '').strip(),
        )
        messages.success(request, f"{student.username}: {days} kun bepul berildi.")
    except services.BillingError as exc:
        messages.error(request, str(exc))

    return redirect('panel:student_detail', user_id=user_id)


# ─────────────────────────── Darsliklar ───────────────────────────


@staff_required
def content(request):
    """Kurslar daraxti: bo'lim -> modul -> dars."""
    categories = Category.objects.prefetch_related(
        Prefetch(
            'modules',
            queryset=Module.objects.order_by('order').prefetch_related(
                Prefetch('lessons', queryset=Lesson.objects.order_by('order').select_related('quiz'))
            ),
        )
    ).order_by('name')

    return render(request, 'panel/content.html', {
        'categories': categories,
        'stats': reports.content_stats(),
        'draft_quizzes': Quiz.objects.filter(is_published=False).count(),
    })


@staff_required
def lesson_edit(request, lesson_id=None):
    """Dars qo'shish yoki tahrirlash."""
    lesson = get_object_or_404(Lesson, pk=lesson_id) if lesson_id else None

    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, instance=lesson)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"«{obj.title}» saqlandi.")
            return redirect('panel:content')
        messages.error(request, "Formada xato bor — quyida ko'rsatilgan.")
    else:
        initial = {}
        module_id = request.GET.get('module')
        if module_id:
            initial['module'] = module_id
        form = LessonForm(instance=lesson, initial=initial)

    return render(request, 'panel/lesson_form.html', {
        'form': form,
        'lesson': lesson,
        'quiz': getattr(lesson, 'quiz', None) if lesson else None,
        'images': lesson.images.all() if lesson else [],
        'image_form': LessonImageForm(),
    })


@require_POST
@staff_required
def lesson_image_add(request, lesson_id):
    """Darsga rasm qo'shish."""
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    form = LessonImageForm(request.POST, request.FILES)

    if form.is_valid():
        image = form.save(commit=False)
        image.lesson = lesson
        if not image.order:
            # Tartib berilmasa oxiriga qo'yamiz — barchasi 0 bo'lib
            # qolsa, ketma-ketlik tasodifiy bo'lardi
            last = lesson.images.order_by('-order').values_list('order', flat=True).first()
            image.order = (last or 0) + 1
        image.save()
        messages.success(request, "Rasm qo'shildi.")
    else:
        messages.error(request, "Rasm yuklanmadi: " + "; ".join(
            f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()
        ))

    return redirect('panel:lesson_edit', lesson_id=lesson.pk)


@require_POST
@staff_required
def lesson_image_delete(request, image_id):
    """
    Rasmni o'chirish.

    FAYL HAM O'CHIRILADI: aks holda diskda hech kimga kerak bo'lmagan
    fayllar to'planib borardi (`prune_orphan_videos` bilan bir xil
    muammo, faqat rasmlarda).
    """
    image = get_object_or_404(LessonImage.objects.select_related('lesson'), pk=image_id)
    lesson_id = image.lesson_id

    image.image.delete(save=False)
    image.delete()
    messages.success(request, "Rasm o'chirildi.")

    return redirect('panel:lesson_edit', lesson_id=lesson_id)


@staff_required
def module_edit(request, module_id=None):
    """Modul qo'shish yoki tahrirlash."""
    module = get_object_or_404(Module, pk=module_id) if module_id else None

    if request.method == 'POST':
        form = ModuleForm(request.POST, instance=module)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"«{obj.title}» moduli saqlandi.")
            return redirect('panel:content')
        messages.error(request, "Formada xato bor.")
    else:
        form = ModuleForm(instance=module)

    return render(request, 'panel/module_form.html', {'form': form, 'module': module})


@staff_required
def quizzes(request):
    """Testlar: qoralamalar va nashr qilinganlar."""
    qs = (
        Quiz.objects.select_related('lesson__module__category')
        .annotate(question_count=Count('questions', distinct=True))
        .order_by('-created_at')
    )

    state = request.GET.get('state', '')
    if state == 'draft':
        qs = qs.filter(is_published=False)
    elif state == 'published':
        qs = qs.filter(is_published=True)
    elif state == 'generated':
        qs = qs.filter(is_generated=True)

    return render(request, 'panel/quizzes.html', {
        'page_obj': _page(request, qs),
        'state': state,
        'draft_count': Quiz.objects.filter(is_published=False).count(),
    })


@require_POST
@staff_required
def quiz_publish(request, quiz_id):
    """
    Testni nashr qilish yoki qoralamaga qaytarish.

    SAVOLSIZ TEST NASHR QILINMAYDI — o'quvchi bo'sh testni ochib,
    "tizim buzuq" degan xulosaga kelardi.
    """
    quiz = get_object_or_404(Quiz.objects.annotate(n=Count('questions')), pk=quiz_id)
    publish = request.POST.get('publish') == '1'

    if publish and quiz.n == 0:
        messages.error(request, f"«{quiz.title}»: savollari yo'q, nashr qilinmadi.")
    else:
        quiz.is_published = publish
        quiz.save(update_fields=['is_published'])
        messages.success(
            request,
            f"«{quiz.title}» {'nashr qilindi' if publish else 'qoralamaga qaytarildi'}.",
        )

    return redirect(request.POST.get('back') or 'panel:quizzes')


# ─────────────────────────── Xabarlar ───────────────────────────


@staff_required
def messages_page(request):
    """Xabar yozish va yuborilganlar tarixi."""
    if request.method == 'POST':
        audience = request.POST.get('audience') or ''
        body = request.POST.get('body') or ''
        target = None

        # Shaxsiy xabar o'quvchi sahifasidan ham yuboriladi — o'sha
        # holatda odam o'z sahifasiga QAYTISHI kerak, aks holda har
        # xabardan keyin ro'yxatga uloqtirilardi.
        back = 'panel:messages'
        if audience == Audience.ONE:
            target_id = request.POST.get('target_user')
            target = User.objects.filter(pk=target_id, is_staff=False).first()
            if target is None:
                messages.error(request, "O'quvchi topilmadi.")
                return redirect('panel:messages')
            back = reverse('panel:student_detail', args=[target.pk])

        try:
            message = messaging.send_now(request.user, audience, body, target)
        except messaging.MessagingError as exc:
            messages.error(request, str(exc))
        else:
            if message.pending_count:
                messages.success(
                    request,
                    f"{message.delivered}/{message.total} yuborildi. "
                    f"Qolgan {message.pending_count} ta navbatda — "
                    "`send_panel_messages` buyrug'i yuboradi.",
                )
            else:
                messages.success(
                    request,
                    f"Yuborildi: {message.delivered} ta"
                    + (f", yetkazilmadi: {message.failed} ta" if message.failed else ""),
                )
        return redirect(back)

    history = PanelMessage.objects.select_related('sent_by', 'target_user').order_by('-created_at')

    return render(request, 'panel/messages.html', {
        'page_obj': _page(request, history, per_page=15),
        'audiences': Audience.choices,
        'preview': messaging.audience_preview(),
        'telegram_ready': messaging.telegram.is_configured(),
        'max_length': messaging.MAX_BODY_LENGTH,
    })


@staff_required
def message_detail(request, message_id):
    """Bitta xabar: kimga ketdi, kim olmadi."""
    message = get_object_or_404(
        PanelMessage.objects.select_related('sent_by', 'target_user'), pk=message_id
    )
    return render(request, 'panel/message_detail.html', {
        'message': message,
        'deliveries': message.deliveries.select_related('user').order_by('state', 'user__username'),
    })


# ─────────────────────────── Kuzatish ───────────────────────────


@staff_required
def monitor(request):
    """Kuzatish: kirish urinishlari, AI Mentor, faollik."""
    tab = request.GET.get('tab', 'logins')

    context = {
        'tab': tab,
        'security': reports.security_stats(),
        'mentor_stats': reports.mentor_stats(),
        'students': reports.student_stats(),
    }

    if tab == 'mentor':
        context['page_obj'] = _page(
            request,
            MentorMessage.objects.select_related('user', 'lesson').order_by('-created_at'),
        )
    elif tab == 'certificates':
        context['page_obj'] = _page(
            request, Certificate.objects.select_related('user').order_by('-issued_at')
        )
    else:
        qs = LoginAttempt.objects.order_by('-created_at')
        only_failed = request.GET.get('failed') == '1'
        if only_failed:
            qs = qs.filter(successful=False)
        context['page_obj'] = _page(request, qs)
        context['only_failed'] = only_failed

    return render(request, 'panel/monitor.html', context)
