from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.plans, name='plans'),
    path('request/', views.create_request, name='create_request'),
    path('request/receipt/', views.mark_receipt_sent, name='mark_receipt_sent'),
    path('request/cancel/', views.cancel_request, name='cancel_request'),
    path('history/', views.my_history, name='history'),
]
