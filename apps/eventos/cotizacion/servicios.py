"""Lo que se hace con una cotización: armar sus conceptos, convertirla en evento y compartirla."""
from datetime import datetime, time, timedelta
from decimal import Decimal
from urllib.parse import quote

from django.db import transaction
from django.utils import timezone

from apps.core.limites import puede_crear
from apps.core.models import Ajustes

from ..models import CategoriaServicio as C
from ..clientes.servicios import vincular
from ..extras import activar, extras_de_conceptos, valores_en_vivo
from ..models import ConceptoCotizacion, ConceptoEvento, Cotizacion, Evento, Paquete, PaqueteServicio, Servicio, numero_whatsapp

DIAS_VIGENCIA = 15

CONDICIONES_BASE = (
    'El anticipo aparta la fecha; el resto se liquida a más tardar 3 días antes del evento.\n'
    'Incluye montaje, operación y desmontaje del equipo.\n'
    'Las horas extra se cobran según esta cotización.\n'
    'Precios en pesos mexicanos.'
)

# Para empezar en un clic: (categoría, nombre, qué incluye, precio, unidad[, extra que activa al venderlo])
CATALOGO_EJEMPLO = [
    (C.PERSONAL, 'DJ profesional', 'DJ con cabina y música para todo el evento', 5000, Servicio.Unidad.EVENTO),
    (C.DIGITAL, 'Experiencia en vivo', 'Pantalla con QR para canciones, saludos y fotos, proyector y panel del DJ', 2500,
     Servicio.Unidad.EVENTO, Servicio.Activa.EN_VIVO),
    (C.DIGITAL, 'Invitación digital', 'Invitación web con confirmación de asistencia y entrada con QR', 1500,
     Servicio.Unidad.EVENTO, Servicio.Activa.INVITACION),
    (C.AUDIO, 'Audio profesional', 'Bocinas, subwoofers y consola para hasta 250 invitados', 4500, Servicio.Unidad.EVENTO),
    (C.AUDIO, 'Micrófono inalámbrico', 'Para brindis y discursos', 350, Servicio.Unidad.PIEZA),
    (C.ILUMINACION, 'Iluminación de ambiente', 'Luces LED de colores para todo el salón', 2500, Servicio.Unidad.EVENTO),
    (C.ILUMINACION, 'Iluminación robótica', 'Cabezas móviles y efectos para la pista', 3500, Servicio.Unidad.EVENTO),
    (C.PISTA, 'Pista iluminada 6×6', 'Pista LED de 6 × 6 m', 7500, Servicio.Unidad.EVENTO),
    (C.PANTALLAS, 'Pantalla LED', 'Pantalla de 3 × 2 m para fotos y videos', 6000, Servicio.Unidad.EVENTO),
    (C.EFECTOS, 'Humo bajo', 'Efecto nube para el primer baile o el vals', 1800, Servicio.Unidad.EVENTO),
    (C.EFECTOS, 'Chisperos fríos', '4 chisperos para la entrada o el vals', 2200, Servicio.Unidad.EVENTO),
    (C.FOTO, 'Cabina de fotos', '3 horas con impresiones ilimitadas', 4500, Servicio.Unidad.EVENTO),
    (C.ANIMACION, 'Hora loca', 'Animadores y accesorios por 1 hora', 3500, Servicio.Unidad.EVENTO),
    (C.EXTRA, 'Hora extra', 'DJ, audio e iluminación', 1500, Servicio.Unidad.HORA),
]
PAQUETES_EJEMPLO = [
    ('Fiesta Esencial', 'Lo indispensable para una gran fiesta', 10500,
     ['DJ profesional', 'Audio profesional', 'Iluminación de ambiente']),
    ('Boda Plata', 'Audio, iluminación y pista para tu boda', 21900,
     ['DJ profesional', 'Audio profesional', 'Micrófono inalámbrico', 'Iluminación de ambiente', 'Iluminación robótica',
      'Pista iluminada 6×6', 'Humo bajo']),
    ('XV Oro', 'La experiencia completa para unos XV años', 32900,
     ['DJ profesional', 'Audio profesional', 'Iluminación de ambiente', 'Iluminación robótica', 'Pista iluminada 6×6',
      'Pantalla LED', 'Chisperos fríos', 'Hora loca', 'Experiencia en vivo', 'Invitación digital']),
]


@transaction.atomic
def cargar_catalogo_ejemplo(agencia):
    """Crea el catálogo de ejemplo (solo lo que no exista con el mismo nombre). Devuelve cuántos servicios creó."""
    existentes = {s.nombre.lower(): s for s in Servicio.objects.filter(agencia=agencia)}
    creados = 0
    for orden, (categoria, nombre, descripcion, precio, unidad, *activa) in enumerate(CATALOGO_EJEMPLO):
        if nombre.lower() not in existentes:
            existentes[nombre.lower()] = Servicio.objects.create(
                agencia=agencia, categoria=categoria, nombre=nombre, descripcion=descripcion,
                precio=Decimal(precio), unidad=unidad, activa=activa[0] if activa else '', orden=orden)
            creados += 1
    nombres = set(Paquete.objects.filter(agencia=agencia).values_list('nombre', flat=True))
    for orden, (nombre, descripcion, precio, servicios) in enumerate(PAQUETES_EJEMPLO):
        if nombre in nombres:
            continue
        paquete = Paquete.objects.create(agencia=agencia, nombre=nombre, descripcion=descripcion, precio=Decimal(precio), orden=orden)
        PaqueteServicio.objects.bulk_create([PaqueteServicio(paquete=paquete, servicio=existentes[s.lower()]) for s in servicios])
    return creados


def nueva_para(usuario):
    """Valores con los que nace una cotización: el próximo sábado a las 19:00, válida 15 días."""
    hoy = timezone.localdate()
    sabado = hoy + timedelta(days=(5 - hoy.weekday()) % 7 or 7)
    return {
        'fecha_evento': timezone.make_aware(datetime.combine(sabado, time(19, 0))),
        'vigencia': hoy + timedelta(days=DIAS_VIGENCIA),
        'condiciones': CONDICIONES_BASE,
    }


def guardar_conceptos(cotizacion, conceptos):
    """Reemplaza los renglones de la cotización con los que mandó el cotizador (ya validados)."""
    cotizacion.conceptos.all().delete()
    ConceptoCotizacion.objects.bulk_create([ConceptoCotizacion(cotizacion=cotizacion, orden=i, **c) for i, c in enumerate(conceptos)])
    cotizacion.__dict__.pop('_subtotal', None)


def lineas_de_servicio(conceptos):
    """Los conceptos como "servicios contratados" del evento (uno por línea, para la orden de servicio)."""
    return '\n'.join(c.texto_servicio for c in conceptos)


def convertir_en_evento(cotizacion, usuario=None):
    """
    Crea el evento confirmado con los datos de la cotización (si aún no lo tiene). Devuelve (evento, motivo):
    sin evento cuando el plan de la agencia ya no permite más eventos este mes.
    """
    if cotizacion.evento_id:
        return cotizacion.evento, ''
    ok, motivo = puede_crear(cotizacion.agencia, 'eventos')
    if not ok:
        return None, motivo
    ajustes = Ajustes.de(cotizacion.agencia_id)
    with transaction.atomic():
        evento = Evento.objects.create(
            agencia_id=cotizacion.agencia_id, colaborador=cotizacion.colaborador, cliente=cotizacion.cliente,
            creado_por=usuario or cotizacion.creado_por,
            nombre_evento=cotizacion.titulo_evento[:200], tipo_evento=cotizacion.tipo_evento, etapa=Evento.Etapa.CONFIRMADO,
            fecha_inicio_evento=cotizacion.fecha_evento, fecha_fin_evento=cotizacion.fecha_fin,
            lugar=cotizacion.lugar, num_invitados=cotizacion.num_invitados,
            cliente_nombre=cotizacion.cliente_nombre, cliente_telefono=cotizacion.cliente_telefono,
            cliente_email=cotizacion.cliente_email, precio_total=cotizacion.total,
            servicios=lineas_de_servicio(cotizacion.conceptos.all()), notas=f'Creado desde la cotización {cotizacion.folio}.',
        )
        valores_en_vivo(evento, ajustes)
        evento.save()
        ConceptoEvento.objects.bulk_create([
            ConceptoEvento(evento=evento, servicio_id=c.servicio_id, paquete_id=c.paquete_id, descripcion=c.descripcion,
                           detalle=c.detalle, cantidad=c.cantidad, unidad=c.unidad, precio_unitario=c.precio_unitario, orden=c.orden)
            for c in cotizacion.conceptos.all()
        ])
        if cotizacion.descuento:  # el descuento de la cotización queda como renglón para que cuadre el precio
            ConceptoEvento.objects.create(evento=evento, descripcion='Descuento', cantidad=Decimal('1'),
                                          precio_unitario=-cotizacion.descuento, orden=999)
        vincular(evento, cotizacion.cliente, usuario)  # el mismo cliente del directorio (o se agrega)
        cotizacion.evento, cotizacion.cliente = evento, evento.cliente
        cotizacion.save(update_fields=['evento', 'cliente', 'actualizado'])
        # Lo que se vendió en la cotización y activa un extra (experiencia en vivo, invitación) queda activo
        evento.extras_activados = activar(evento, extras_de_conceptos(cotizacion.conceptos.all()))
    return evento, ''


def aceptar(cotizacion, usuario=None, nombre=''):
    """La marca como aceptada y crea el evento. Devuelve (evento, motivo) como convertir_en_evento."""
    cotizacion.estado = Cotizacion.Estado.ACEPTADA
    cotizacion.respondida_el = timezone.now()
    cotizacion.aceptada_por = (nombre or (usuario.get_full_name() if usuario else '') or cotizacion.cliente_nombre)[:150]
    cotizacion.save(update_fields=['estado', 'respondida_el', 'aceptada_por', 'actualizado'])
    return convertir_en_evento(cotizacion, usuario)


def url_whatsapp(cotizacion, url_publica, nombre_negocio):
    texto = (f'Hola {cotizacion.cliente_nombre.split(" ")[0]}, te comparto la cotización {cotizacion.folio} de '
             f'{nombre_negocio} para {cotizacion.titulo_evento}: {url_publica}\n'
             f'Ahí puedes verla, descargarla en PDF y aceptarla. ¡Quedo atento!')
    numero = numero_whatsapp(cotizacion.cliente_telefono)
    return f'https://wa.me/{numero}?text={quote(texto)}' if numero else f'https://wa.me/?text={quote(texto)}'


def duplicar(cotizacion, usuario):
    copia = Cotizacion.objects.create(
        agencia_id=cotizacion.agencia_id, colaborador=cotizacion.colaborador, creado_por=usuario, cliente=cotizacion.cliente,
        cliente_nombre=cotizacion.cliente_nombre, cliente_telefono=cotizacion.cliente_telefono,
        cliente_email=cotizacion.cliente_email, nombre_evento=cotizacion.nombre_evento, tipo_evento=cotizacion.tipo_evento,
        fecha_evento=cotizacion.fecha_evento, duracion_horas=cotizacion.duracion_horas, lugar=cotizacion.lugar,
        num_invitados=cotizacion.num_invitados, descuento=cotizacion.descuento,
        anticipo_porcentaje=cotizacion.anticipo_porcentaje, condiciones=cotizacion.condiciones,
        notas_internas=cotizacion.notas_internas, vigencia=timezone.localdate() + timedelta(days=DIAS_VIGENCIA),
    )
    ConceptoCotizacion.objects.bulk_create([
        ConceptoCotizacion(cotizacion=copia, servicio_id=c.servicio_id, paquete_id=c.paquete_id, descripcion=c.descripcion,
                           detalle=c.detalle, cantidad=c.cantidad, unidad=c.unidad, precio_unitario=c.precio_unitario, orden=c.orden)
        for c in cotizacion.conceptos.all()
    ])
    return copia
