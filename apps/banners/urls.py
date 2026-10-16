from django.urls import path

from . import views

app_name = 'banners'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nuevo/', views.BannerCrear.as_view(), name='crear'),
    path('<int:pk>/editar/', views.BannerEditar.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
]
