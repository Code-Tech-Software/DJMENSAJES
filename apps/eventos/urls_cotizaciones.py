from django.urls import path

from .cotizacion import views

app_name = 'cotizaciones'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nueva/', views.editar, name='nueva'),

    path('catalogo/', views.catalogo, name='catalogo'),
    path('catalogo/ejemplo/', views.catalogo_ejemplo, name='catalogo_ejemplo'),
    path('catalogo/servicios/nuevo/', views.ServicioCrear.as_view(), name='servicio_crear'),
    path('catalogo/servicios/<int:pk>/editar/', views.ServicioEditar.as_view(), name='servicio_editar'),
    path('catalogo/servicios/<int:pk>/eliminar/', views.servicio_eliminar, name='servicio_eliminar'),
    path('catalogo/paquetes/nuevo/', views.PaqueteCrear.as_view(), name='paquete_crear'),
    path('catalogo/paquetes/<int:pk>/editar/', views.PaqueteEditar.as_view(), name='paquete_editar'),
    path('catalogo/paquetes/<int:pk>/eliminar/', views.paquete_eliminar, name='paquete_eliminar'),

    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/pdf/', views.pdf, name='pdf'),
    path('<int:pk>/whatsapp/', views.whatsapp, name='whatsapp'),
    path('<int:pk>/enviada/', views.marcar_enviada, name='enviada'),
    path('<int:pk>/aceptar/', views.aceptar_cotizacion, name='aceptar'),
    path('<int:pk>/crear-evento/', views.crear_evento, name='crear_evento'),
    path('<int:pk>/rechazar/', views.rechazar, name='rechazar'),
    path('<int:pk>/duplicar/', views.duplicar_cotizacion, name='duplicar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
]
