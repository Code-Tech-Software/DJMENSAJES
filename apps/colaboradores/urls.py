from django.urls import path

from . import views

app_name = 'colaboradores'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nuevo/', views.ColaboradorCrear.as_view(), name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/editar/', views.ColaboradorEditar.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
]
