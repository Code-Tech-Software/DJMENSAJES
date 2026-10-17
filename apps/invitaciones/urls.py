from django.urls import path, re_path

from . import editor, views

app_name = 'invitaciones'

urlpatterns = [
    path('', views.indice, name='indice'),
    path('evento/<int:pk>/', views.panel, name='panel'),
    path('evento/<int:pk>/editor/', editor.editor, name='editar'),
    path('evento/<int:pk>/editor/guardar/', editor.guardar, name='guardar'),
    path('evento/<int:evento_pk>/lugares/nuevo/', editor.UbicacionCrear.as_view(), name='lugar_crear'),
    path('lugares/<int:pk>/editar/', editor.UbicacionEditar.as_view(), name='lugar_editar'),
    path('evento/<int:evento_pk>/personas/nuevo/', editor.MencionCrear.as_view(), name='mencion_crear'),
    path('personas/<int:pk>/editar/', editor.MencionEditar.as_view(), name='mencion_editar'),
    path('evento/<int:pk>/galeria/subir/', editor.subir_fotos, name='fotos_subir'),
    re_path(r'^(?P<seccion>lugares|personas|galeria)/(?P<pk>\d+)/eliminar/$', editor.eliminar, name='elemento_eliminar'),
    re_path(r'^(?P<seccion>lugares|personas|galeria)/(?P<pk>\d+)/mover/(?P<direccion>arriba|abajo)/$',
            editor.mover, name='elemento_mover'),
    path('evento/<int:pk>/plantilla/', views.cambiar_plantilla, name='cambiar_plantilla'),
    path('evento/<int:pk>/publicar/', views.publicar, name='publicar'),
    re_path(r'^evento/(?P<pk>\d+)/anfitriones/(?P<accion>crear|regenerar|desactivar)/$',
            views.enlace_anfitriones, name='enlace_anfitriones'),
    path('evento/<int:pk>/invitados/nuevo/', views.InvitadoCrear.as_view(), name='invitado_crear'),
    path('evento/<int:pk>/invitados/importar/', views.ImportarInvitados.as_view(), name='importar'),
    path('evento/<int:pk>/invitados/exportar/', views.exportar, name='exportar'),
    path('evento/<int:pk>/entrada/', views.checkin, name='checkin'),

    path('invitados/<int:pk>/editar/', views.InvitadoEditar.as_view(), name='invitado_editar'),
    path('invitados/<int:pk>/eliminar/', views.invitado_eliminar, name='invitado_eliminar'),
    path('invitados/<int:pk>/enviada/', views.marcar_enviada, name='marcar_enviada'),
    path('invitados/<int:pk>/entrada/', views.checkin_marcar, name='checkin_marcar'),
    path('pase/<str:token>/', views.checkin_escaneo, name='checkin_escaneo'),
]
