from django.urls import path, re_path

from .consola import agencias, bitacora, dashboard, pagos, planes, sesion, usuarios
from .consola.contacto import ContactoEditar

app_name = 'plataforma'

urlpatterns = [
    path('', dashboard.dashboard, name='dashboard'),

    path('agencias/', agencias.agencias, name='agencias'),
    path('agencias/nueva/', agencias.AgenciaCrear.as_view(), name='agencia_crear'),
    path('agencias/<int:pk>/', agencias.agencia, name='agencia'),
    path('agencias/<int:pk>/editar/', agencias.AgenciaEditar.as_view(), name='agencia_editar'),
    path('agencias/<int:pk>/suspender/', agencias.suspender, name='suspender'),
    re_path(r'^agencias/(?P<pk>\d+)/extender/(?P<meses>1|3|12)/$', agencias.extender, name='extender'),
    path('agencias/<int:pk>/administrador/', agencias.AdministradorCrear.as_view(), name='administrador_crear'),
    path('agencias/<int:pk>/pagos/nuevo/', pagos.PagoCrear.as_view(), name='agencia_pago'),

    path('usuarios/', usuarios.usuarios, name='usuarios'),
    path('usuarios/nuevo/', usuarios.UsuarioCrear.as_view(), name='usuario_crear'),
    path('usuarios/<int:pk>/editar/', usuarios.UsuarioEditar.as_view(), name='usuario_editar'),
    path('usuarios/<int:pk>/activar/', usuarios.activar, name='usuario_activar'),
    path('usuarios/<int:pk>/nueva-clave/', usuarios.nueva_clave, name='nueva_clave'),
    path('usuarios/<int:pk>/entrar/', sesion.entrar_como, name='entrar_como'),
    path('salir/', sesion.salir_de, name='salir_de'),

    path('pagos/', pagos.pagos, name='pagos'),
    path('pagos/nuevo/', pagos.PagoCrear.as_view(), name='pago_crear'),
    path('pagos/<int:pk>/eliminar/', pagos.eliminar, name='pago_eliminar'),

    path('planes/', planes.planes, name='planes'),
    path('planes/nuevo/', planes.PlanCrear.as_view(), name='plan_crear'),
    path('planes/<int:pk>/editar/', planes.PlanEditar.as_view(), name='plan_editar'),
    path('planes/<int:pk>/eliminar/', planes.eliminar, name='plan_eliminar'),

    path('bitacora/', bitacora.bitacora, name='bitacora'),
    path('contacto/', ContactoEditar.as_view(), name='contacto'),
]
