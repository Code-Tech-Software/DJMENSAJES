"""Difusión de mensajes en tiempo real por los grupos de Channels."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def grupo_dj(evento_id):
    return f'envivo_{evento_id}_dj'


def grupo_estado(evento_id):
    return f'envivo_{evento_id}_estado'


def grupo_pantalla(evento_id):
    return f'envivo_{evento_id}_pantalla'


def _enviar(grupo, datos):
    capa = get_channel_layer()
    if capa is None:
        return
    try:
        async_to_sync(capa.group_send)(grupo, {'type': 'difundir', 'datos': datos})
    except Exception:  # un fallo de Redis no debe impedir guardar el mensaje
        logger.exception('No se pudo difundir al grupo %s', grupo)


def notificar_nuevo(mensaje):
    _enviar(grupo_dj(mensaje.evento_id), {'tipo': 'nuevo', 'mensaje': mensaje.a_dict()})
    if mensaje.en_pantalla:
        notificar_pantalla(mensaje)


def notificar_cambio(mensaje, pantalla_cambio=False):
    _enviar(grupo_dj(mensaje.evento_id), {'tipo': 'cambio', 'mensaje': mensaje.a_dict()})
    _enviar(grupo_estado(mensaje.evento_id), {'tipo': 'estado', 'id': mensaje.pk, 'estatus': mensaje.estatus})
    if pantalla_cambio:
        notificar_pantalla(mensaje)


def notificar_pantalla(mensaje):
    if mensaje.en_pantalla and mensaje.estatus != mensaje.Estatus.DESCARTADO:
        _enviar(grupo_pantalla(mensaje.evento_id), {'tipo': 'mostrar', 'mensaje': mensaje.a_dict_pantalla()})
    else:
        _enviar(grupo_pantalla(mensaje.evento_id), {'tipo': 'quitar', 'id': mensaje.pk})


def notificar_evento(evento):
    """Avisa a todas las pantallas que cambió la configuración (p. ej. se pausó)."""
    datos = {'tipo': 'config', 'activo': evento.estado}
    for grupo in (grupo_dj(evento.pk), grupo_estado(evento.pk), grupo_pantalla(evento.pk)):
        _enviar(grupo, datos)
