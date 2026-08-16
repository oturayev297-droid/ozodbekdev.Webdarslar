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
    path('oquvchilar/<int:user_id>/ruxsat/', views.student_approval, name='student_approval'),

    # ── Darsliklar ──
    path('darslar/', views.content, name='content'),
    path('darslar/yangi/', views.lesson_edit, name='lesson_new'),
    path('darslar/<int:lesson_id>/', views.lesson_edit, name='lesson_edit'),
    path('darslar/<int:lesson_id>/rasm/', views.lesson_image_add, name='lesson_image_add'),
    path('rasmlar/<int:image_id>/ochirish/', views.lesson_image_delete, name='lesson_image_delete'),
    path('modullar/yangi/', views.module_edit, name='module_new'),
    path('modullar/<int:module_id>/', views.module_edit, name='module_edit'),
    path('bolimlar/yangi/', views.category_edit, name='category_new'),
    path('bolimlar/<int:category_id>/', views.category_edit, name='category_edit'),
    path('bolimlar/<int:category_id>/ochirish/', views.category_delete, name='category_delete'),
    path('loyihalar/', views.projects, name='projects'),
    path('loyihalar/yangi/', views.project_edit, name='project_new'),
    path('loyihalar/<int:project_id>/', views.project_edit, name='project_edit'),
    path('loyihalar/<int:project_id>/ochirish/', views.project_delete, name='project_delete'),
    path('testlar/', views.quizzes, name='quizzes'),
    path('testlar/<int:quiz_id>/savollar/', views.quiz_questions, name='quiz_questions'),
    path('testlar/<int:quiz_id>/savol/', views.question_save, name='question_save'),
    path('savollar/<int:question_id>/ochirish/', views.question_delete, name='question_delete'),
    path('testlar/<int:quiz_id>/nashr/', views.quiz_publish, name='quiz_publish'),

    # ── Xabarlar ──
    path('xabarlar/', views.messages_page, name='messages'),
    path('xabarlar/<int:message_id>/', views.message_detail, name='message_detail'),

    # ── Ota-onalar ──
    path('ota-onalar/', views.parents, name='parents'),
    path('ota-onalar/boglash/', views.parent_link_create, name='parent_link_create'),
    path('ota-onalar/<int:link_id>/uzish/', views.parent_link_delete, name='parent_link_delete'),

    # ── Sozlamalar ──
    path('sozlamalar/', views.settings_page, name='settings'),
    path('sozlamalar/kartalar/', views.settings_cards, name='settings_cards'),
    path('sozlamalar/narx/', views.settings_price, name='settings_price'),

    # ── Kuzatish ──
    path('kuzatish/', views.monitor, name='monitor'),
]
