from django.urls import path

from . import views

urlpatterns = [
    path('', views.landing, name='landing'),

    # Darslar
    path('lessons/', views.lessons, name='lessons'),
    path('lessons/<int:lesson_id>/', views.lessons, name='lessons_detail'),
    path('lessons/<int:lesson_id>/video/', views.lesson_video, name='lesson_video'),
    path('lessons/<int:lesson_id>/complete/', views.complete_lesson, name='complete_lesson'),

    path('dashboard/', views.dashboard, name='dashboard'),

    # Kod muharriri
    path('editor/', views.editor, name='editor'),
    path('editor/<int:challenge_id>/', views.editor, name='editor_detail'),
    path('editor/<int:challenge_id>/solution/', views.challenge_solution, name='challenge_solution'),

    path('projects/', views.projects, name='projects'),

    # Testlar
    path('quizzes/', views.quizzes, name='quizzes'),
    path('quiz/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),
    path('quiz/<int:quiz_id>/submit/', views.submit_quiz, name='submit_quiz'),

    # Auth
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),

    # Sertifikatlar
    path('certificates/', views.my_certificates, name='my_certificates'),
    path('certificates/<str:code>/pdf/', views.certificate_pdf, name='certificate_pdf'),
    path('verify/', views.verify_certificate, name='verify_certificate'),

    # Parolni tiklash
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/', views.reset_password, name='reset_password'),
]
