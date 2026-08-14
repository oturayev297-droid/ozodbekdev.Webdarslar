"""
Panel manzillari
================

`/admin/` (Django'ning standart paneli) O'CHIRILMAYDI: u zaxira yo'l
bo'lib qoladi. Bu panel kundalik ish uchun, Django admin esa nozik
holatlar (model darajasidagi tuzatish, migratsiyadan keyingi tekshiruv)
uchun kerak bo'ladi.
"""

from django.urls import path

from . import auth, views

app_name = 'panel'

urlpatterns = [
    # ── Kirish / chiqish ──
    path('login/', auth.panel_login, name='login'),
    path('logout/', auth.panel_logout, name='logout'),
    path('forgot-password/', auth.panel_forgot_password, name='forgot_password'),
    path('reset-password/', auth.panel_reset_password, name='reset_password'),

    # ── Bosh sahifa ──
    path('', views.dashboard, name='dashboard'),

    # ── Moliya ──
    path('moliya/', views.finance, name='finance'),
    path('moliya/davrlar/', views.periods, name='periods'),
    path('tolovlar/', views.payments, name='payments'),
    path('tolovlar/<int:request_id>/amal/', views.payment_action, name='payment_action'),
    path('tolovlar/tizimlar/', views.gateway_log, name='gateways'),

    # ── O'quvchilar ──
    path('oquvchilar/', views.students, name='students'),
    path('oquvchilar/<int:user_id>/', views.student_detail, name='student_detail'),
    path('oquvchilar/<int:user_id>/bepul/', views.student_grant, name='student_grant'),

    # ── Darsliklar ──
    path('darslar/', views.content, name='content'),
    path('darslar/yangi/', views.lesson_edit, name='lesson_new'),
    path('darslar/<int:lesson_id>/', views.lesson_edit, name='lesson_edit'),
    path('modullar/yangi/', views.module_edit, name='module_new'),
    path('modullar/<int:module_id>/', views.module_edit, name='module_edit'),
    path('testlar/', views.quizzes, name='quizzes'),
    path('testlar/<int:quiz_id>/nashr/', views.quiz_publish, name='quiz_publish'),

    # ── Xabarlar ──
    path('xabarlar/', views.messages_page, name='messages'),
    path('xabarlar/<int:message_id>/', views.message_detail, name='message_detail'),

    # ── Kuzatish ──
    path('kuzatish/', views.monitor, name='monitor'),
]
