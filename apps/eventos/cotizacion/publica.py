"""La cotización que ve el cliente con su enlace: la revisa, descarga el PDF y la acepta (se crea el evento)."""
from urllib.parse import quote

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.marca import Marca
from apps.core.modulos import tiene

from ..models import Cotizacion
from .servicios import aceptar
from .views import respuesta_pdf


def _cotizacion(token):
    cotizacion = get_object_or_404(Cotizacion.objects.select_related('agencia__plan', 'colaborador', 'evento'), token=token)
    if not tiene(cotizacion.agencia, 'cotizaciones'):
        raise Http404
    return cotizacion


def cotizacion_publica(request, token):
    cotizacion = _cotizacion(token)
    es_del_equipo = request.user.is_authenticated and request.user.agencia_id == cotizacion.agencia_id
    if not cotizacion.vista_el and not es_del_equipo:  # "visto": la primera vez que la abre alguien de fuera
        cotizacion.vista_el = timezone.now()
        cotizacion.save(update_fields=['vista_el'])
    marca = Marca(cotizacion)
    dudas = ''
    if marca.whatsapp_url:
        dudas = f'{marca.whatsapp_url}?text={quote(f"Hola, tengo dudas sobre la cotización {cotizacion.folio}")}'
    return render(request, 'cotizaciones/publica.html', {
        'cotizacion': cotizacion, 'marca': marca, 'whatsapp_dudas': dudas,
        'recien_aceptada': request.GET.get('aceptada') == '1', 'es_del_equipo': es_del_equipo,
    })


def cotizacion_publica_pdf(request, token):
    return respuesta_pdf(_cotizacion(token), request, descargar=True)


@require_POST
def cotizacion_aceptar(request, token):
    cotizacion = _cotizacion(token)
    if cotizacion.abierta:
        nombre = request.POST.get('nombre', '').strip()[:150]
        aceptar(cotizacion, None, nombre or cotizacion.cliente_nombre)
        return redirect(f'{cotizacion.url_cliente()}?aceptada=1')
    return redirect(cotizacion.url_cliente())
