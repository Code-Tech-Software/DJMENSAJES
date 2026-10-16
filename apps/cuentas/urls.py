from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'cuentas'

urlpatterns = [
    path('login/', views.iniciar_sesion, name='login'),
    path('logout/', views.CerrarSesion.as_view(), name='logout'),
    path('registro/', RedirectView.as_view(pattern_name='cuentas:usuarios'), name='registro'),

    path('perfil/', views.perfil, name='perfil'),
    path('perfil/editar/', views.EditarPerfil.as_view(), name='editar_perfil'),
    path('perfil/contrasena/', views.CambiarContrasena.as_view(), name='cambiar_contrasena'),

    path('usuarios/', views.usuarios, name='usuarios'),
    path('usuarios/nuevo/', views.UsuarioCrear.as_view(), name='usuario_crear'),
    path('usuarios/<int:pk>/editar/', views.UsuarioEditar.as_view(), name='usuario_editar'),
    path('usuarios/<int:pk>/contrasena/', views.UsuarioContrasena.as_view(), name='usuario_contrasena'),
    path('usuarios/<int:pk>/activar/', views.usuario_activar, name='usuario_activar'),
]
