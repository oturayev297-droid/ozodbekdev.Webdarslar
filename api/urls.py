"""
API manzillari — `/api/v1/`

VERSIYA MANZILDA. Frontend alohida deploy qilinadi va backend bilan
bir vaqtda yangilanmaydi: Vercel'dagi eski frontend Railway'dagi yangi
backendga bir necha daqiqa murojaat qilib turishi mumkin. Versiya
bo'lmasa, buzuvchi o'zgarish kiritilganda eski frontend jimgina
ishlamay qolardi.
"""

from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    # ── Autentifikatsiya ──
    path('auth/csrf/', views.csrf, name='csrf'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/me/', views.me, name='me'),
    path('auth/password-reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path(
        'auth/password-reset/confirm/',
        views.PasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),

    # ── Kurslar va darslar ──
    path('courses/', views.CourseListView.as_view(), name='courses'),
    path('courses/<slug:slug>/', views.CourseDetailView.as_view(), name='course_detail'),
    path('lessons/<int:pk>/', views.LessonDetailView.as_view(), name='lesson_detail'),
    path('lessons/<int:pk>/complete/', views.LessonCompleteView.as_view(), name='lesson_complete'),

    # ── Testlar ──
    path('quizzes/', views.QuizListView.as_view(), name='quizzes'),
    path('quizzes/<int:pk>/', views.QuizDetailView.as_view(), name='quiz_detail'),
    path('quizzes/<int:pk>/submit/', views.QuizSubmitView.as_view(), name='quiz_submit'),

    # ── Obuna ──
    path('subscription/', views.subscription_state, name='subscription'),
    path('subscription/request/', views.PaymentRequestCreateView.as_view(), name='payment_request'),
    path('subscription/receipt/', views.PaymentReceiptView.as_view(), name='payment_receipt'),
    path('subscription/card/', views.payment_card, name='payment_card'),

    # ── Sertifikatlar ──
    path('certificates/', views.my_certificates, name='certificates'),
    # OCHIQ: ish beruvchining tizimda hisobi yo'q
    path('certificates/verify/', views.verify_certificate, name='verify_certificate'),

    # ── AI Mentor ──
    path('mentor/ask/', views.MentorAskView.as_view(), name='mentor_ask'),

    # ── Dashboard ──
    path('dashboard/', views.dashboard, name='dashboard'),
]
