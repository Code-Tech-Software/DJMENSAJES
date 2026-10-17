from django.urls import path

from . import anfitriones

app_name = 'anfitriones'

urlpatterns = [
    path('<str:token>/', anfitriones.panel, name='panel'),
    path('<str:token>/invitados/nuevo/', anfitriones.InvitadoCrear.as_view(), name='invitado_crear'),
    path('<str:token>/invitados/importar/', anfitriones.Importar.as_view(), name='importar'),
    path('<str:token>/invitados/exportar/', anfitriones.exportar, name='exportar'),
    path('<str:token>/invitados/<int:pk>/editar/', anfitriones.InvitadoEditar.as_view(), name='invitado_editar'),
    path('<str:token>/invitados/<int:pk>/eliminar/', anfitriones.invitado_eliminar, name='invitado_eliminar'),
    path('<str:token>/invitados/<int:pk>/enviada/', anfitriones.marcar_enviada, name='marcar_enviada'),
]
