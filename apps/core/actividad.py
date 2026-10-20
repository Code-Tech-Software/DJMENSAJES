"""Feed de actividad reciente (dashboard y campana de notificaciones)."""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.core.modulos import tiene
from apps.envivo.models import Mensaje
from apps.eventos.models import Cotizacion, Evento
from apps.invitaciones.models import Invitado


def actividad_reciente(usuario, limite=10, desde=None):
    eventos = Evento.objects.visibles_para(usuario)
    elementos = []

    respuestas = (Invitado.objects.filter(evento__in=eventos, respondido_en__isnull=False)
                  .select_related('evento').order_by('-respondido_en'))
    if desde:
        respuestas = respuestas.filter(respondido_en__gt=desde)
    for invitado in respuestas[:limite]:
        confirmo = invitado.estado == Invitado.Estado.CONFIRMADO
        elementos.append({
            'fecha': invitado.respondido_en,
            'icono': 'ph ph-user-check' if confirmo else 'ph ph-user-minus',
            'tono': 'tone-success' if confirmo else 'tone-danger',
            'texto': (f'<strong>{_e(invitado.nombre)}</strong> '
                      + (f'confirmó {invitado.pases_confirmados} pase(s)' if confirmo else 'no podrá asistir')
                      + f' a <strong>{_e(invitado.evento.nombre_evento)}</strong>'),
            'url': reverse('invitaciones:panel', args=[invitado.evento_id]),
        })

    vip = (Mensaje.objects.filter(evento__in=eventos, vip=True)
           .select_related('evento').order_by('-fecha_creacion'))
    if desde:
        vip = vip.filter(fecha_creacion__gt=desde)
    for mensaje in vip[:limite]:
        elementos.append({
            'fecha': mensaje.fecha_creacion,
            'icono': 'ph ph-crown-simple',
            'tono': 'tone-gold',
            'texto': (f'<strong>{_e(mensaje.nombre)}</strong> (VIP) envió '
                      + ('una canción' if mensaje.tipo == 'cancion' else 'un saludo')
                      + f' en <strong>{_e(mensaje.evento.nombre_evento)}</strong>'),
            'url': reverse('eventos:detalle', args=[mensaje.evento_id]) + '#mensajes',
        })

    nuevos = eventos.select_related('creado_por').order_by('-creado')
    if desde:
        nuevos = nuevos.filter(creado__gt=desde)
    for evento in nuevos[:limite]:
        autor = evento.creado_por.nombre_corto if evento.creado_por else 'Alguien'
        elementos.append({
            'fecha': evento.creado,
            'icono': 'ph ph-calendar-check',
            'tono': '',
            'texto': f'<strong>{_e(autor)}</strong> registró el evento <strong>{_e(evento.nombre_evento)}</strong>',
            'url': evento.get_absolute_url(),
        })

    cotizaciones = _cotizaciones(usuario)
    aceptadas = cotizaciones.filter(estado=Cotizacion.Estado.ACEPTADA, respondida_el__isnull=False).order_by('-respondida_el')
    if desde:
        aceptadas = aceptadas.filter(respondida_el__gt=desde)
    for c in aceptadas[:limite]:
        elementos.append({
            'fecha': c.respondida_el,
            'icono': 'ph ph-seal-check',
            'tono': 'tone-success',
            'texto': f'<strong>{_e(c.aceptada_por or c.cliente_nombre)}</strong> aceptó la cotización <strong>{c.folio}</strong>',
            'url': c.get_absolute_url(),
        })
    vistas = cotizaciones.filter(vista_el__isnull=False).order_by('-vista_el')
    if desde:
        vistas = vistas.filter(vista_el__gt=desde)
    for c in vistas[:limite]:
        elementos.append({
            'fecha': c.vista_el,
            'icono': 'ph ph-eye',
            'tono': 'tone-live',
            'texto': f'<strong>{_e(c.cliente_nombre)}</strong> abrió la cotización <strong>{c.folio}</strong>',
            'url': c.get_absolute_url(),
        })

    elementos.sort(key=lambda x: x['fecha'], reverse=True)
    return elementos[:limite]


def _cotizaciones(usuario):
    """Las cotizaciones que cuentan en la actividad (ninguna si el plan de la agencia no incluye el módulo)."""
    if not tiene(usuario.agencia if usuario.agencia_id else None, 'cotizaciones'):
        return Cotizacion.objects.none()
    return Cotizacion.objects.visibles_para(usuario)


def recordatorios(usuario):
    """Eventos que empiezan en las próximas 48 horas."""
    ahora = timezone.now()
    return list(Evento.objects.visibles_para(usuario).vigentes()
                .filter(fecha_inicio_evento__gt=ahora, fecha_inicio_evento__lte=ahora + timedelta(hours=48))
                .order_by('fecha_inicio_evento')[:5])


def contar_no_vistas(usuario):
    desde = usuario.notificaciones_vistas_en or (timezone.now() - timedelta(days=7))
    eventos = Evento.objects.visibles_para(usuario)
    cotizaciones = _cotizaciones(usuario)
    return (Invitado.objects.filter(evento__in=eventos, respondido_en__gt=desde).count()
            + Mensaje.objects.filter(evento__in=eventos, vip=True, fecha_creacion__gt=desde).count()
            + cotizaciones.filter(estado=Cotizacion.Estado.ACEPTADA, respondida_el__gt=desde).count()
            + cotizaciones.filter(vista_el__gt=desde).count())


def _e(texto):
    from django.utils.html import escape
    return escape(texto)
