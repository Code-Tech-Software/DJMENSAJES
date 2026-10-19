"""
Panel de los anfitriones (los novios, la quinceañera, la familia…). Entran con un enlace privado, sin
cuenta, y administran su lista de invitados: agregar, importar, editar, quitar y enviar por WhatsApp.
No pueden cambiar el diseño de la invitación, publicarla ni registrar entradas.
"""
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.mixins import es_ajax, respuesta_ok
from apps.core.marca import Marca
from apps.core.models import Ajustes
from apps.eventos.models import Evento

from .models import Invitacion, Invitado
from .views import (
    ImportarInvitadosBase, InvitadoCrearBase, InvitadoEditarBase, clave_anfitrion, csv_invitados,
    lista_invitados, registrar_envio,
)


def invitacion_de(token):
    """La invitación de ese enlace; un enlace desactivado, cambiado o de un evento cancelado da 404."""
    return get_object_or_404(
        Invitacion.objects.select_related('evento__colaborador').exclude(evento__etapa=Evento.Etapa.CANCELADO),
        token_anfitriones=token,
    )


def panel(request, token):
    invitacion = invitacion_de(token)
    evento = invitacion.evento
    # Con esto el anfitrión puede ver la invitación aunque siga en borrador (y sin contar como visita)
    request.session[clave_anfitrion(invitacion)] = token
    inicio = timezone.localtime(evento.fecha_inicio_evento)
    contexto = lista_invitados(request, evento, invitacion, token=token)
    contexto.update({
        'evento': evento,
        'invitacion': invitacion,
        'token': token,
        'inicio': inicio,
        'faltan': (inicio.date() - timezone.localdate()).days,
        'url_publica': request.build_absolute_uri(invitacion.get_absolute_url()),
        'ajustes': Ajustes.de(evento.agencia_id),
        'marca': Marca(evento),
    })
    return render(request, 'invitaciones/anfitriones.html', contexto)


class AnfitrionMixin:
    """Valida el enlace y limita todo a la lista de ese evento."""

    def dispatch(self, request, *args, **kwargs):
        self.invitacion = invitacion_de(kwargs['token'])
        if request.method == 'GET' and not es_ajax(request):
            # Los formularios solo se abren en modal desde el panel
            return redirect('anfitriones:panel', kwargs['token'])
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return [self.template_modal]

    def get_evento(self):
        return self.invitacion.evento


class InvitadoCrear(AnfitrionMixin, InvitadoCrearBase):
    pass


class InvitadoEditar(AnfitrionMixin, InvitadoEditarBase):
    def get_queryset(self):
        return Invitado.objects.filter(evento_id=self.invitacion.evento_id)


class Importar(AnfitrionMixin, ImportarInvitadosBase):
    pass


def _invitado(token, pk):
    invitacion = invitacion_de(token)
    return get_object_or_404(Invitado, pk=pk, evento_id=invitacion.evento_id)


@require_POST
def invitado_eliminar(request, token, pk):
    invitado = _invitado(token, pk)
    invitado.delete()
    return respuesta_ok(request, f'Se quitó a {invitado.nombre} de la lista.')


@require_POST
def marcar_enviada(request, token, pk):
    return registrar_envio(_invitado(token, pk))


def exportar(request, token):
    invitacion = invitacion_de(token)
    return csv_invitados(request, invitacion.evento, invitacion)
