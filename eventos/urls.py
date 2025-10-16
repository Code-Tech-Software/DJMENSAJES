from django.urls import path
from . import views

urlpatterns = [
    path('nuevo/', views.crear_evento, name='crear_evento'),
    path('mis_eventos/', views.mis_eventos, name='mis_eventos'),
    path('<int:id>/editar/', views.editar_evento, name='editar_evento'),
    path('<int:id>/eliminar/', views.eliminar_evento, name='eliminar_evento'),

    path('evento/<int:evento_id>/', views.pantalla_evento, name='pantalla_evento'),
    path('evento/<int:evento_id>/enviar/', views.enviar_mensaje, name='enviar_mensaje'),

    path('evento/<int:evento_id>/panel_dj/', views.panel_dj, name='panel_dj'),
    path('evento/<int:evento_id>/detalle/', views.detalle_evento, name='detalle_evento'),

]
