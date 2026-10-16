from django.urls import path

from . import views

app_name = 'envivo'

urlpatterns = [
    # Pantalla de invitados (el QR apunta aquí: URL corta)
    path('e/<str:codigo>/', views.invitado, name='invitado'),
    path('e/<str:codigo>/enviar/', views.enviar, name='enviar'),
    path('e/<str:codigo>/vip/', views.vip, name='vip'),
    path('e/<str:codigo>/nombre/', views.cambiar_nombre, name='nombre'),
    path('e/<str:codigo>/mis-mensajes/', views.mis_mensajes, name='mis_mensajes'),

    # Proyector y DJ
    path('envivo/pantalla/<str:codigo>/', views.pantalla, name='pantalla'),
    path('envivo/dj/<str:token>/', views.dj, name='dj'),
    path('envivo/dj/<str:token>/mensajes/', views.dj_mensajes, name='dj_mensajes'),
    path('envivo/dj/<str:token>/mensajes/<int:pk>/<str:accion>/', views.dj_accion, name='dj_accion'),
    path('envivo/dj/<str:token>/recepcion/', views.dj_recepcion, name='dj_recepcion'),

    # Compatibilidad con los enlaces y QR de la versión anterior
    path('eventos/evento/<int:evento_id>/', views.legado_invitados),
    path('eventos/evento/<int:evento_id>/panel_dj/', views.legado_dj),
    path('eventos/evento/<int:evento_id>/detalle/', views.legado_pantalla),
]
