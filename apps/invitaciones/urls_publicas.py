from django.urls import path

from . import views

app_name = 'invitacion_publica'

urlpatterns = [
    path('<slug:slug>/', views.invitacion_general, name='general'),
    path('<slug:slug>/confirmar/', views.rsvp_abierto, name='rsvp_abierto'),
    path('<slug:slug>/calendario.ics', views.calendario_ics, name='ics'),
    path('<slug:slug>/<str:token>/', views.invitacion_personal, name='personal'),
    path('<slug:slug>/<str:token>/confirmar/', views.rsvp, name='rsvp'),
]
