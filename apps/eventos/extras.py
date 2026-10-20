"""
Extras que la agencia vende por evento: la experiencia en vivo y la invitación digital.

Un evento nace solo con sus datos. Sus extras se activan:
- a mano, desde el detalle del evento;
- solos, al vender un servicio del catálogo marcado "al venderlo activa…" (en el evento o en una cotización
  aceptada), también si viene dentro de un paquete;
- la experiencia en vivo, en todos los eventos nuevos si la agencia lo eligió en sus Ajustes.
Siempre que el plan de la agencia incluya ese módulo. Quitar un servicio no desactiva nada: eso se hace a mano.
"""
from apps.core.models import Ajustes
from apps.core.modulos import tiene

from .models import PaqueteServicio, Servicio

EN_VIVO = Servicio.Activa.EN_VIVO
INVITACION = Servicio.Activa.INVITACION
MODULO = {EN_VIVO: 'en_vivo', INVITACION: 'invitaciones'}
NOMBRES = dict(Servicio.Activa.choices)


def _ids(conceptos, campo):
    """Los ids de servicio o paquete de conceptos guardados (objetos) o recién validados (dicts)."""
    valores = (c.get(f'{campo}_id') if isinstance(c, dict) else getattr(c, f'{campo}_id') for c in conceptos)
    return {v for v in valores if v}


def extras_de_conceptos(conceptos):
    """Qué extras activan esos conceptos: {'en_vivo', 'invitacion'} (o parte)."""
    conceptos = list(conceptos)
    servicios, paquetes = _ids(conceptos, 'servicio'), _ids(conceptos, 'paquete')
    extras = set(Servicio.objects.filter(pk__in=servicios).exclude(activa='').values_list('activa', flat=True)) if servicios else set()
    if paquetes:
        extras |= set(PaqueteServicio.objects.filter(paquete_id__in=paquetes).exclude(servicio__activa='')
                      .values_list('servicio__activa', flat=True))
    return extras


def tiene_invitacion(evento):
    return hasattr(evento, 'invitacion')


def activar(evento, extras):
    """Activa los extras que pide la lista (si el plan los incluye). Devuelve los nombres de los que se activaron."""
    activados = []
    if EN_VIVO in extras and not evento.con_en_vivo and tiene(evento.agencia, MODULO[EN_VIVO]):
        evento.con_en_vivo = True
        evento.save(update_fields=['con_en_vivo', 'actualizado'])
        activados.append(NOMBRES[EN_VIVO])
    if INVITACION in extras and tiene(evento.agencia, MODULO[INVITACION]) and not tiene_invitacion(evento):
        from apps.invitaciones.views import obtener_invitacion  # (crea la invitación con sus valores sugeridos)
        obtener_invitacion(evento)
        activados.append(NOMBRES[INVITACION])
    return activados


def valores_en_vivo(evento, ajustes=None):
    """Con lo que nace la experiencia en vivo de un evento nuevo: los valores de los Ajustes de su agencia."""
    ajustes = ajustes or Ajustes.de(evento.agencia_id)
    evento.cooldown = ajustes.cooldown
    evento.permitir_saludos = ajustes.permitir_saludos
    evento.permitir_canciones = ajustes.permitir_canciones
    evento.permitir_fotos = ajustes.permitir_fotos and tiene(evento.agencia, 'fotos')
    evento.moderar_pantalla = ajustes.moderar_pantalla
    evento.mensaje_bienvenida = ajustes.mensaje_bienvenida
    evento.con_en_vivo = bool(ajustes.en_vivo_por_defecto and tiene(evento.agencia, 'en_vivo'))
    return evento
