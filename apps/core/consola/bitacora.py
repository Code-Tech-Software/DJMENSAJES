"""Bitácora: lo que pasa en la plataforma, con filtros."""
from django.core.paginator import Paginator
from django.shortcuts import render

from ..models import Agencia, Bitacora
from . import solo_plataforma


@solo_plataforma
def bitacora(request):
    agencia = request.GET.get('agencia', '')
    accion = request.GET.get('accion', '')
    q = request.GET.get('q', '').strip()
    lista = Bitacora.objects.select_related('actor', 'agencia', 'usuario')
    if agencia == 'eventpro':
        lista = lista.filter(agencia__isnull=True)
    elif agencia.isdigit():
        lista = lista.filter(agencia_id=agencia)
    if accion in Bitacora.Accion.values:
        lista = lista.filter(accion=accion)
    elif accion == 'sin_accesos':  # oculta los inicios de sesión, que son la mayoría
        lista = lista.exclude(accion=Bitacora.Accion.INICIO_SESION)
    if q:
        lista = lista.filter(detalle__icontains=q) | lista.filter(actor__username__icontains=q) | lista.filter(usuario__username__icontains=q)
    pagina = Paginator(lista, 50).get_page(request.GET.get('pagina'))
    filtros = '&'.join(f'{k}={v}' for k, v in (('agencia', agencia), ('accion', accion), ('q', q)) if v)
    return render(request, 'core/consola/bitacora.html', {
        'pagina': pagina, 'filtros': filtros, 'agencia': agencia, 'accion': accion, 'q': q,
        'agencias': Agencia.objects.order_by('nombre'), 'acciones': Bitacora.Accion.choices,
    })
