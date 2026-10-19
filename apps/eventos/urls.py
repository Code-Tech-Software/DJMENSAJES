from django.urls import path

from . import views

app_name = 'eventos'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('calendario/', views.calendario, name='calendario'),
    path('calendario/datos/', views.api_calendario, name='api_calendario'),
    path('en-vivo/', views.centro_envivo, name='centro_envivo'),
    path('nuevo/', views.EventoCrear.as_view(), name='crear'),
    path('disponibilidad/', views.disponibilidad, name='disponibilidad'),

    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/vista-rapida/', views.vista_rapida, name='vista_rapida'),
    path('<int:pk>/editar/', views.EventoEditar.as_view(), name='editar'),
    path('<int:pk>/proyector/', views.ProyectorEditar.as_view(), name='proyector'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('<int:pk>/duplicar/', views.duplicar, name='duplicar'),
    path('<int:pk>/interaccion/', views.alternar_estado, name='alternar_estado'),
    path('<int:pk>/orden/', views.orden, name='orden'),
    path('<int:pk>/qr.png', views.qr_png, name='qr_png'),

    path('<int:evento_pk>/itinerario/nuevo/', views.ActividadCrear.as_view(), name='actividad_crear'),
    path('itinerario/<int:pk>/editar/', views.ActividadEditar.as_view(), name='actividad_editar'),
    path('itinerario/<int:pk>/eliminar/', views.actividad_eliminar, name='actividad_eliminar'),
    path('<int:evento_pk>/pagos/nuevo/', views.PagoCrear.as_view(), name='pago_crear'),
    path('pagos/<int:pk>/eliminar/', views.pago_eliminar, name='pago_eliminar'),
]
