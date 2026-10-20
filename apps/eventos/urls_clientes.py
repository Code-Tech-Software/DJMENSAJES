from django.urls import path

from .clientes import views

app_name = 'clientes'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nuevo/', views.ClienteCrear.as_view(), name='crear'),
    path('exportar/', views.exportar, name='exportar'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/editar/', views.ClienteEditar.as_view(), name='editar'),
    path('<int:pk>/fusionar/', views.Fusionar.as_view(), name='fusionar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
]
