"""El portal que abre el cliente con su enlace: su evento, sus pagos y su cuestionario musical."""
from urllib.parse import quote

from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.marca import Marca
from apps.core.modulos import tiene

from ..models import PortalCliente
from .forms import CuestionarioForm


def _portal(token):
    return get_object_or_404(PortalCliente.objects.select_related('evento__agencia__plan', 'evento__colaborador'),
                             token=token, activo=True)


def _contexto(request, portal, form):
    evento = portal.evento
    marca = Marca(evento)
    ahora = timezone.now()
    invitacion = getattr(evento, 'invitacion', None)
    contacto = ''
    if marca.whatsapp_url:
        contacto = f'{marca.whatsapp_url}?text={quote(f"Hola, te escribo por mi evento {evento.nombre_evento}")}'
    return {
        'portal': portal, 'evento': evento, 'marca': marca, 'form': form,
        'conceptos': evento.conceptos.all(), 'itinerario': evento.itinerario_en_orden(),
        'pagos': evento.pagos.all() if portal.mostrar_pagos else [],
        'datos_pago': marca.ajustes.datos_pago if portal.mostrar_pagos else '',
        'invitacion': invitacion if invitacion and invitacion.publicada and tiene(evento.agencia, 'invitaciones') else None,
        'album': (evento.url_album() if evento.con_en_vivo and evento.fecha_fin_evento < ahora
                  and tiene(evento.agencia, 'en_vivo') and tiene(evento.agencia, 'album') else ''),
        'contacto': contacto,
        'comprobante': f'{marca.whatsapp_url}?text={quote(f"Hola, te envío mi comprobante de pago del evento {evento.nombre_evento}")}' if marca.whatsapp_url else '',
        'es_del_equipo': request.user.is_authenticated and request.user.agencia_id == evento.agencia_id,
        'guardado': request.GET.get('guardado') == '1',
        'dias': (timezone.localdate(evento.fecha_inicio_evento) - timezone.localdate()).days,
    }


def portal(request, token):
    portal = _portal(token)
    contexto = _contexto(request, portal, CuestionarioForm(instance=portal))
    if not portal.visto_el and not contexto['es_del_equipo']:  # "visto": la primera vez que lo abre el cliente
        portal.visto_el = timezone.now()
        portal.save(update_fields=['visto_el'])
    return render(request, 'eventos/portal/publica.html', contexto)


@require_POST
def portal_musica(request, token):
    portal = _portal(token)
    if not portal.editable:
        return redirect(portal.get_absolute_url() + '#musica')
    form = CuestionarioForm(request.POST, instance=portal)
    if form.is_valid():
        form.save()
        return redirect(portal.get_absolute_url() + '?guardado=1#musica')
    return render(request, 'eventos/portal/publica.html', _contexto(request, portal, form), status=422)
