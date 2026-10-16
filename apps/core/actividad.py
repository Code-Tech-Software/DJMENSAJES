"""Feed de actividad reciente (dashboard y campana de notificaciones)."""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.envivo.models import Mensaje
from apps.eventos.models import Evento
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
            'icono': 'ri-user-follow-line' if confirmo else 'ri-user-unfollow-line',
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
            'icono': 'ri-vip-crown-2-line',
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
            'icono': 'ri-calendar-check-line',
            'tono': '',
            'texto': f'<strong>{_e(autor)}</strong> registró el evento <strong>{_e(evento.nombre_evento)}</strong>',
            'url': evento.get_absolute_url(),
        })

    elementos.sort(key=lambda x: x['fecha'], reverse=True)
    return elementos[:limite]


def recordatorios(usuario):
    """Eventos que empiezan en las próximas 48 horas."""
    ahora = timezone.now()
    return list(Evento.objects.visibles_para(usuario).vigentes()
                .filter(fecha_inicio_evento__gt=ahora, fecha_inicio_evento__lte=ahora + timedelta(hours=48))
                .order_by('fecha_inicio_evento')[:5])


def contar_no_vistas(usuario):
    desde = usuario.notificaciones_vistas_en or (timezone.now() - timedelta(days=7))
    eventos = Evento.objects.visibles_para(usuario)
    return (Invitado.objects.filter(evento__in=eventos, respondido_en__gt=desde).count()
            + Mensaje.objects.filter(evento__in=eventos, vip=True, fecha_creacion__gt=desde).count())


def _e(texto):
    from django.utils.html import escape
    return escape(texto)
