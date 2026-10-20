"""
Asistente del formulario de eventos: textos según el tipo de evento, sugerencias tomadas de los eventos
anteriores de la agencia (lugares y clientes), itinerarios base y disponibilidad del día.
"""
from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from .models import ActividadItinerario, Evento

# tipo: (etiqueta del nombre, ejemplo, ayuda)
TEXTOS_TIPO = {
    'boda': ('Nombres de los novios', 'Ej. Ana & Luis', 'Así se verá en las pantallas y en la invitación.'),
    'quinse': ('Nombre de la quinceañera', 'Ej. Sofía', 'Así se verá en las pantallas y en la invitación.'),
    'cumple': ('¿Quién cumple años?', 'Ej. Don Roberto · 60 años', 'Puedes incluir los años que cumple.'),
    'fiesta': ('Nombre de la fiesta', 'Ej. Fiesta Blanca 2026', 'Así se verá en las pantallas.'),
    'bautizo': ('Nombre del bebé', 'Ej. Mateo', 'Así se verá en las pantallas y en la invitación.'),
    'graduacion': ('Generación o graduado', 'Ej. Generación 2023–2026', 'Así se verá en las pantallas.'),
    'corporativo': ('Empresa o nombre del evento', 'Ej. Posada Constructora del Norte', 'Así se verá en las pantallas.'),
    'aniversario': ('Pareja o motivo', 'Ej. Bodas de plata Carmen & José', 'Así se verá en las pantallas y en la invitación.'),
    'otro': ('Nombre del evento', 'Ej. Ana & Luis', 'Así se verá en las pantallas, p. ej. "Ana & Luis" o "Sofía".'),
}

ETAPAS = {
    'cotizacion': 'Aún no confirma: queda como cotización y no cuenta en tus cobros.',
    'confirmado': 'El cliente ya confirmó: aparece en tu agenda y en lo que tienes por cobrar.',
    'cancelado': 'No se realizará: se guarda en tu historial, fuera de la agenda.',
}

DURACIONES = (4, 5, 6, 7, 8)

# Itinerario base por tipo: (minutos desde el inicio, actividad, icono)
ITINERARIOS = {
    'boda': [(0, 'Llegada de invitados', 'recepcion'), (60, 'Entrada de los novios', 'vals'), (75, 'Primer baile', 'vals'),
             (90, 'Brindis', 'brindis'), (105, 'Cena', 'cena'), (180, 'Apertura de pista', 'fiesta'), (270, 'Pastel', 'pastel'),
             (300, 'Hora loca', 'fiesta')],
    'quinse': [(0, 'Llegada de invitados', 'recepcion'), (60, 'Entrada de la quinceañera', 'vals'), (75, 'Vals', 'vals'),
               (90, 'Brindis', 'brindis'), (105, 'Cena', 'cena'), (165, 'Baile sorpresa', 'vals'), (180, 'Apertura de pista', 'fiesta'),
               (270, 'Pastel', 'pastel'), (300, 'Hora loca', 'fiesta')],
    'cumple': [(0, 'Llegada de invitados', 'recepcion'), (60, 'Cena', 'cena'), (120, 'Apertura de pista', 'fiesta'),
               (210, 'Pastel y mañanitas', 'pastel'), (240, 'Hora loca', 'fiesta')],
    'fiesta': [(0, 'Apertura', 'recepcion'), (60, 'Apertura de pista', 'fiesta'), (180, 'Hora loca', 'fiesta')],
    'bautizo': [(0, 'Llegada de invitados', 'recepcion'), (45, 'Comida', 'cena'), (120, 'Pastel', 'pastel'), (150, 'Fiesta', 'fiesta')],
    'graduacion': [(0, 'Llegada de invitados', 'recepcion'), (45, 'Entrada de la generación', 'vals'), (60, 'Brindis', 'brindis'),
                   (75, 'Cena', 'cena'), (135, 'Vals de graduación', 'vals'), (150, 'Apertura de pista', 'fiesta'),
                   (270, 'Hora loca', 'fiesta')],
    'corporativo': [(0, 'Registro de asistentes', 'recepcion'), (30, 'Bienvenida', 'otro'), (60, 'Cena', 'cena'),
                    (120, 'Reconocimientos', 'otro'), (150, 'Fiesta', 'fiesta')],
    'aniversario': [(0, 'Llegada de invitados', 'recepcion'), (45, 'Renovación de votos', 'ceremonia'), (75, 'Brindis', 'brindis'),
                    (90, 'Cena', 'cena'), (150, 'Baile de la pareja', 'vals'), (165, 'Apertura de pista', 'fiesta'),
                    (240, 'Pastel', 'pastel')],
    'otro': [(0, 'Llegada de invitados', 'recepcion'), (60, 'Cena', 'cena'), (120, 'Fiesta', 'fiesta')],
}


def actividades_base(tipo, inicio, fin):
    """Las del itinerario base que caben en el horario del evento: [(hora, actividad, icono)]."""
    duracion = (fin - inicio).total_seconds() / 60
    inicio = timezone.localtime(inicio) if timezone.is_aware(inicio) else inicio
    return [((inicio + timedelta(minutes=m)).time(), titulo, icono)
            for m, titulo, icono in ITINERARIOS.get(tipo, ITINERARIOS['otro']) if m < duracion]


def crear_itinerario(evento):
    ActividadItinerario.objects.bulk_create([
        ActividadItinerario(evento=evento, hora=hora, titulo=titulo, icono=icono)
        for hora, titulo, icono in actividades_base(evento.tipo_evento, evento.fecha_inicio_evento, evento.fecha_fin_evento)
    ])


def sugerencias(usuario, limite=40):
    """Lugares y clientes de los eventos anteriores que el usuario puede ver (lo más reciente primero)."""
    eventos = (Evento.objects.visibles_para(usuario).order_by('-creado')
               .values('lugar', 'direccion', 'url_mapa', 'cliente_nombre', 'cliente_telefono', 'cliente_email')[:200])
    lugares, clientes, vistos_l, vistos_c = [], [], set(), set()
    for e in eventos:
        clave = e['lugar'].strip().lower()
        if clave and clave not in vistos_l and len(lugares) < limite:
            vistos_l.add(clave)
            lugares.append({'lugar': e['lugar'].strip(), 'direccion': e['direccion'], 'url_mapa': e['url_mapa']})
        clave = e['cliente_nombre'].strip().lower()
        if clave and clave not in vistos_c and len(clientes) < limite:
            vistos_c.add(clave)
            clientes.append({'nombre': e['cliente_nombre'].strip(), 'telefono': e['cliente_telefono'], 'email': e['cliente_email']})
    return {'lugares': lugares, 'clientes': clientes}


def eventos_cercanos(usuario, inicio, fin, excepto=None):
    """Eventos (no cancelados) del usuario que empiezan ese mismo día o que se cruzan con el horario."""
    dia = timezone.localtime(inicio).date()
    desde = timezone.make_aware(datetime.combine(dia, time.min))
    eventos = (Evento.objects.visibles_para(usuario).vigentes()
               .filter(Q(fecha_inicio_evento__gte=desde, fecha_inicio_evento__lt=desde + timedelta(days=1))
                       | Q(fecha_inicio_evento__lt=fin, fecha_fin_evento__gt=inicio))
               .select_related('colaborador').order_by('fecha_inicio_evento'))
    if excepto:
        eventos = eventos.exclude(pk=excepto)
    return [(e, e.fecha_inicio_evento < fin and e.fecha_fin_evento > inicio) for e in eventos[:6]]
