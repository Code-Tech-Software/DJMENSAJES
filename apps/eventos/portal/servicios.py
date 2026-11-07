"""El portal de cada evento: se crea la primera vez que se necesita y se comparte por WhatsApp."""
from datetime import timedelta
from urllib.parse import quote

from django.utils import timezone

from ..models import PortalCliente, numero_whatsapp

DIAS_ANTES = 5  # hasta cuándo puede cambiar su música, por omisión


def limite_sugerido(evento):
    """Cinco días antes del evento; si ya no da tiempo, la víspera (o sin límite si el evento es mañana)."""
    hoy = timezone.localdate()
    dia = timezone.localdate(evento.fecha_inicio_evento)
    for dias in (DIAS_ANTES, 1):
        limite = dia - timedelta(days=dias)
        if limite >= hoy:
            return limite
    return None


def obtener_portal(evento):
    portal = getattr(evento, '_portal_cache', None)
    if portal is None:
        portal, _ = PortalCliente.objects.get_or_create(evento=evento, defaults={'fecha_limite': limite_sugerido(evento)})
        evento._portal_cache = portal
    return portal


def url_whatsapp(portal, url, nombre_negocio):
    evento = portal.evento
    nombre = (evento.cliente_nombre or '').split(' ')[0]
    texto = (f'Hola{" " + nombre if nombre else ""}, te compartimos el portal de tu evento "{evento.nombre_evento}" '
             f'con {nombre_negocio}: {url}\n'
             'Ahí puedes ver los detalles, tus pagos y llenar tu cuestionario musical para que el DJ ponga justo lo que te gusta.')
    numero = numero_whatsapp(evento.cliente_telefono)
    return f'https://wa.me/{numero}?text={quote(texto)}' if numero else f'https://wa.me/?text={quote(texto)}'
