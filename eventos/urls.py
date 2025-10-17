from django.urls import path
from . import views
from .views import SonidoDJListView, SonidoDJUpdateView, sonidodj_eliminar, SonidoDJCreateView, BannerCreateView, \
    BannerListView, BannerUpdateView, banner_eliminar

urlpatterns = [


    path('nuevo/', views.crear_evento, name='crear_evento'),
    path('mis_eventos/', views.mis_eventos, name='mis_eventos'),
    path('<int:id>/editar/', views.editar_evento, name='editar_evento'),

    path('eventos/eliminar/<int:evento_id>/', views.eliminar_evento, name='eliminar_evento'),

    path('evento/<int:evento_id>/', views.pantalla_evento, name='pantalla_evento'),
    path('evento/<int:evento_id>/enviar/', views.enviar_mensaje, name='enviar_mensaje'),

    path('evento/<int:evento_id>/panel_dj/', views.panel_dj, name='panel_dj'),
    path('evento/<int:evento_id>/detalle/', views.detalle_evento, name='detalle_evento'),

    # URLs para SonidoDJ
    path('sonidos/', SonidoDJListView.as_view(), name='sonidodj_list'),
    path('sonidos/nuevo/', SonidoDJCreateView.as_view(), name='sonidodj_crear'),
    path('sonidos/editar/<int:pk>/', SonidoDJUpdateView.as_view(), name='sonidodj_editar'),
    # ✅ URL MODIFICADA PARA APUNTAR A LA FUNCIÓN
    path('sonidos/eliminar/<int:pk>/', sonidodj_eliminar, name='sonidodj_eliminar'),

    # URLs para Banner
    path('banners/', BannerListView.as_view(), name='banner_list'),
    path('banners/nuevo/', BannerCreateView.as_view(), name='banner_crear'),
    path('banners/editar/<int:pk>/', BannerUpdateView.as_view(), name='banner_editar'),
    # ✅ URL MODIFICADA PARA APUNTAR A LA FUNCIÓN
    path('banners/eliminar/<int:pk>/', banner_eliminar, name='banner_eliminar'),

]
