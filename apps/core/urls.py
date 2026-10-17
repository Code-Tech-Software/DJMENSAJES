from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('buscar/', views.buscar, name='buscar'),
    path('ajustes/', views.ajustes, name='ajustes'),
    path('notificaciones/', views.notificaciones, name='notificaciones'),
    path('notificaciones/leidas/', views.notificaciones_leidas, name='notificaciones_leidas'),
]
