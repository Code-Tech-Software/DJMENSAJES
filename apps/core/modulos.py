"""
Módulos del plan de cada agencia: qué secciones y opciones puede usar, y su bolsa de fotos al mes.

Sin plan (o sin agencia, como las cuentas de EventPro) todo está incluido. Lo básico —calendario, eventos,
itinerario, pagos y orden de servicio— no es un módulo: siempre está.
"""
from collections import defaultdict
from datetime import datetime
from functools import wraps

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from .mixins import es_ajax

# módulo: (campo del plan, nombre, icono, qué incluye)
MODULOS = {
    'invitaciones': ('con_invitaciones', 'Invitaciones digitales', 'ph ph-envelope-open',
                     'Diseño de la invitación, lista de invitados, confirmaciones, enlace de anfitriones y entrada con QR.'),
    'en_vivo': ('con_en_vivo', 'Experiencia en vivo', 'ph ph-broadcast',
                'Pantalla de invitados con QR, canciones y saludos, proyector y panel del DJ.'),
    'fotos': ('con_fotos', 'Fotos de invitados', 'ph ph-camera', 'Los invitados suben fotos que el DJ aprueba para la pantalla.'),
    'album': ('con_album', 'Álbum digital', 'ph ph-images', 'Álbum en línea con las fotos y saludos del evento.'),
    'banners': ('con_banners', 'Banners propios', 'ph ph-image', 'Subir sus propios fondos además de los de EventPro.'),
}
# Sin experiencia en vivo no hay de dónde salgan fotos ni álbum
DEPENDE_DE = {'fotos': 'en_vivo', 'album': 'en_vivo'}


def _plan(agencia):
    return agencia.plan if agencia is not None and agencia.plan_id else None


def tiene(agencia, modulo):
    plan = _plan(agencia)
    if plan is None:
        return True
    if modulo == 'subagencias':
        return plan.max_colaboradores != 0
    incluido = getattr(plan, MODULOS[modulo][0])
    padre = DEPENDE_DE.get(modulo)
    return incluido and (padre is None or getattr(plan, MODULOS[padre][0]))


def modulos_de(agencia):
    """{'invitaciones': True, 'en_vivo': False, …, 'subagencias': True} para mostrar u ocultar secciones."""
    datos = {m: tiene(agencia, m) for m in MODULOS}
    datos['subagencias'] = tiene(agencia, 'subagencias')
    return datos


def lista_modulos(agencia):
    """Para mostrar en la consola y en "Mi plan": cada módulo con si está incluido."""
    return [{'clave': m, 'nombre': n, 'icono': i, 'descripcion': d, 'incluido': tiene(agencia, m)}
            for m, (_, n, i, d) in MODULOS.items()]


# --- Bolsa de fotos al mes ------------------------------------------------------------------------
#
# El plan da una bolsa de fotos al mes para todos los eventos de la agencia (cuenta el mes en que es el
# evento). Al organizar cada evento se aparta una parte (Evento.limite_fotos). Los eventos sin apartado
# comparten lo que quede libre, y las fotos que ya recibieron también ocupan la bolsa.

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre')


def bolsa_de(agencia):
    """Fotos al mes que da el plan (None = sin límite)."""
    plan = _plan(agencia)
    return plan.max_fotos_mes if plan else None


def _ocupadas_por_mes(agencia, excepto=None, **filtro):
    """{(año, mes): fotos} apartadas en eventos más las ya recibidas en eventos sin apartado."""
    from apps.envivo.models import Mensaje
    from apps.eventos.models import Evento
    eventos = Evento.objects.filter(agencia=agencia, **filtro)
    if excepto is not None and excepto.pk:
        eventos = eventos.exclude(pk=excepto.pk)
    con_apartado = eventos.filter(limite_fotos__isnull=False).exclude(etapa=Evento.Etapa.CANCELADO)
    ocupadas = defaultdict(int)
    for fila in (con_apartado.annotate(mes=TruncMonth('fecha_inicio_evento')).order_by()
                 .values('mes').annotate(n=Sum('limite_fotos'))):
        ocupadas[(fila['mes'].year, fila['mes'].month)] += fila['n']
    sueltas = Mensaje.objects.filter(tipo=Mensaje.Tipo.FOTO, evento__in=eventos.exclude(pk__in=con_apartado.values('pk')))
    for fila in (sueltas.annotate(mes=TruncMonth('evento__fecha_inicio_evento')).order_by()
                 .values('mes').annotate(n=Count('id'))):
        ocupadas[(fila['mes'].year, fila['mes'].month)] += fila['n']
    return ocupadas


def bolsa_del_mes(agencia, anio, mes, excepto=None):
    """{'total', 'ocupadas', 'libres', 'mes'} de la bolsa de ese mes, o None si el plan no tiene límite."""
    total = bolsa_de(agencia)
    if total is None:
        return None
    ocupadas = _ocupadas_por_mes(agencia, excepto, fecha_inicio_evento__year=anio,
                                 fecha_inicio_evento__month=mes).get((anio, mes), 0)
    return {'total': total, 'ocupadas': ocupadas, 'libres': max(0, total - ocupadas), 'mes': MESES[mes - 1]}


def bolsa_por_mes(agencia, meses, excepto=None):
    """{'2026-11': libres, …} de los meses pedidos [(año, mes), …] para el formulario del evento."""
    total = bolsa_de(agencia)
    if total is None or not meses:
        return {}
    anio, mes = min(meses)
    desde = timezone.make_aware(datetime(anio, mes, 1))
    ocupadas = _ocupadas_por_mes(agencia, excepto, fecha_inicio_evento__gte=desde)
    return {f'{a}-{m:02d}': max(0, total - ocupadas.get((a, m), 0)) for a, m in meses}


def limite_fotos(evento):
    """Cuántas fotos puede recibir el evento en total (None = sin límite)."""
    total = bolsa_de(evento.agencia)
    if total is None:
        return evento.limite_fotos
    if evento.limite_fotos is not None:
        return min(evento.limite_fotos, total)
    # Sin apartado: lo que no ocupan los demás eventos del mes (sus propias fotos ya caben ahí)
    fecha = timezone.localtime(evento.fecha_inicio_evento)
    return bolsa_del_mes(evento.agencia, fecha.year, fecha.month, excepto=evento)['libres']


def fotos_subidas(evento):
    from apps.envivo.models import Mensaje
    return evento.mensajes.filter(tipo=Mensaje.Tipo.FOTO).count()


def fotos_disponibles(evento):
    """Cuántas fotos más se pueden subir (None = sin límite)."""
    limite = limite_fotos(evento)
    return None if limite is None else max(0, limite - fotos_subidas(evento))


# --- Bloqueo de secciones del panel ---------------------------------------------------------------

def modulo_no_incluido(request, modulo):
    from .models import Ajustes
    nombre = MODULOS[modulo][1] if modulo in MODULOS else 'Esta sección'
    if es_ajax(request):
        return JsonResponse({'ok': False, 'message': f'Tu plan no incluye {nombre.lower()}.'}, status=403)
    return render(request, 'core/modulo_no_incluido.html', {
        'modulo': MODULOS.get(modulo), 'contacto': Ajustes.plataforma(),
    }, status=403)


def requiere_modulo(modulo):
    """Decorador para vistas del panel: la agencia de quien entra debe tener el módulo en su plan."""
    marca = f'requiere_modulo_{modulo}'

    def decorador(vista):
        if getattr(vista, marca, False):
            return vista

        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            usuario = getattr(request, 'user', None)
            if usuario is not None and usuario.is_authenticated and usuario.agencia_id and not tiene(usuario.agencia, modulo):
                return modulo_no_incluido(request, modulo)
            return vista(request, *args, **kwargs)

        setattr(envoltura, marca, True)
        return envoltura
    return decorador
