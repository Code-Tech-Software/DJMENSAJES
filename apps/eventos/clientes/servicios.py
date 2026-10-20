"""Reglas del directorio: reconocer al mismo cliente, ligarlo a sus eventos y cotizaciones, fusionar y resumir."""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from ..models import Cliente, Cotizacion, Evento, Pago, normalizar_telefono

ABIERTAS = (Cotizacion.Estado.BORRADOR, Cotizacion.Estado.ENVIADA)
DINERO = DecimalField(max_digits=14, decimal_places=2)


def buscar_existente(agencia_id, nombre, telefono='', email=''):
    """
    El cliente de la agencia que es la misma persona: mismo teléfono o mismo correo; si no, el mismo nombre
    (solo si hay uno y su teléfono o correo no dicen lo contrario).
    """
    clientes = Cliente.objects.filter(agencia_id=agencia_id).order_by('pk')
    telefono = normalizar_telefono(telefono)
    email = (email or '').strip().lower()
    if len(telefono) >= 7:
        cliente = clientes.filter(telefono_normalizado=telefono).first()
        if cliente:
            return cliente
    if email:
        cliente = clientes.filter(email__iexact=email).first()
        if cliente:
            return cliente
    nombre = ' '.join((nombre or '').split())
    mismos = list(clientes.filter(nombre__iexact=nombre)[:2]) if nombre else []
    if len(mismos) == 1:
        cliente = mismos[0]
        otro_telefono = telefono and cliente.telefono_normalizado and cliente.telefono_normalizado != telefono
        otro_correo = email and cliente.email and cliente.email != email
        if not (otro_telefono or otro_correo):
            return cliente
    return None


def vincular(objeto, cliente=None, usuario=None):
    """
    Liga un evento o una cotización (ya guardados) con su cliente del directorio: el que se eligió, el que ya
    existe con esos datos o uno nuevo. Lo que le falte al cliente (teléfono, correo) se completa con lo del evento
    y viceversa. Devuelve el cliente (None si no hay nombre de cliente).
    """
    nombre = ' '.join((objeto.cliente_nombre or '').split())
    if cliente is not None and cliente.agencia_id != objeto.agencia_id:
        cliente = None  # nunca el cliente de otra agencia
    if cliente is None and not nombre:
        if objeto.cliente_id:
            objeto.cliente = None
            objeto.save(update_fields=['cliente'])
        return None
    if cliente is None:
        cliente = buscar_existente(objeto.agencia_id, nombre, objeto.cliente_telefono, objeto.cliente_email)
    if cliente is None:
        cliente = Cliente.objects.create(
            agencia_id=objeto.agencia_id, nombre=nombre[:150], telefono=objeto.cliente_telefono,
            email=objeto.cliente_email, creado_por=usuario or objeto.creado_por,
        )
    else:
        cambios = ['actualizado']  # su última actividad
        if objeto.cliente_telefono and not cliente.telefono:
            cliente.telefono = objeto.cliente_telefono
            cambios.append('telefono')
        if objeto.cliente_email and not cliente.email:
            cliente.email = objeto.cliente_email
            cambios.append('email')
        cliente.save(update_fields=cambios)

    cambios = ['cliente'] if objeto.cliente_id != cliente.pk else []
    objeto.cliente = cliente
    for campo, valor in (('cliente_nombre', cliente.nombre), ('cliente_telefono', cliente.telefono), ('cliente_email', cliente.email)):
        if not getattr(objeto, campo) and valor:
            setattr(objeto, campo, valor)
            cambios.append(campo)
    if cambios:
        objeto.save(update_fields=cambios)
    return cliente


def actualizar_contacto(cliente, antes):
    """
    Al corregir el nombre, teléfono o correo de un cliente se corrigen también en sus eventos próximos y en sus
    cotizaciones abiertas (los pasados se quedan como se acordaron). Devuelve cuántos se actualizaron.
    """
    eventos = cliente.eventos.filter(fecha_fin_evento__gte=timezone.now())
    cotizaciones = cliente.cotizaciones.filter(estado__in=ABIERTAS)
    tocados = set()
    for campo_cliente, campo in (('nombre', 'cliente_nombre'), ('telefono', 'cliente_telefono'), ('email', 'cliente_email')):
        viejo, nuevo = antes.get(campo_cliente, ''), getattr(cliente, campo_cliente)
        if viejo == nuevo:
            continue
        for consulta, clave in ((eventos, 'e'), (cotizaciones, 'c')):
            filtro = {f'{campo}__iexact': viejo} if campo == 'cliente_email' else {campo: viejo}
            ids = list(consulta.filter(**filtro).values_list('pk', flat=True))
            consulta.filter(pk__in=ids).update(**{campo: nuevo})
            tocados.update((clave, pk) for pk in ids)
    return len(tocados)


def fusionar(destino, origen):
    """Junta dos fichas de la misma persona: todo pasa a destino, se completan sus datos y origen se borra."""
    with transaction.atomic():
        Evento.objects.filter(cliente=origen).update(cliente=destino)
        Cotizacion.objects.filter(cliente=origen).update(cliente=destino)
        for campo in ('telefono', 'email', 'origen'):
            if not getattr(destino, campo) and getattr(origen, campo):
                setattr(destino, campo, getattr(origen, campo))
        if origen.notas.strip():
            destino.notas = f'{destino.notas.strip()}\n{origen.notas.strip()}'.strip()
        destino.creado = min(destino.creado, origen.creado)
        destino.save()
        origen.delete()
    return destino


# --- Resumen de cada cliente -------------------------------------------------------------------------

def _contar(consulta, por='cliente'):
    return Coalesce(Subquery(consulta.values(por).annotate(n=Count('pk')).values('n')[:1], output_field=IntegerField()), 0)


def _sumar(consulta, campo, por='cliente'):
    return Coalesce(Subquery(consulta.values(por).annotate(t=Sum(campo)).values('t')[:1], output_field=DINERO),
                    Value(Decimal('0')), output_field=DINERO)


def con_resumen(clientes, usuario):
    """
    Agrega a cada cliente su historial con la agencia, contando solo los eventos y cotizaciones que el usuario
    puede ver: eventos (sin cancelados), confirmados, cotizaciones, lo contratado, lo pagado, el saldo y las
    fechas de su evento próximo y del último.
    """
    ahora = timezone.now()
    visibles = Evento.objects.visibles_para(usuario)
    eventos = visibles.filter(cliente=OuterRef('pk')).order_by()
    vigentes = eventos.exclude(etapa=Evento.Etapa.CANCELADO)
    confirmados = eventos.filter(etapa=Evento.Etapa.CONFIRMADO)
    cotizaciones = Cotizacion.objects.visibles_para(usuario).filter(cliente=OuterRef('pk')).order_by()
    pagos = Pago.objects.filter(evento__in=visibles.filter(etapa=Evento.Etapa.CONFIRMADO), evento__cliente=OuterRef('pk')).order_by()
    return clientes.annotate(
        n_eventos=_contar(vigentes),
        n_confirmados=_contar(confirmados),
        n_cotizaciones=_contar(cotizaciones),
        n_abiertas=_contar(cotizaciones.filter(estado__in=ABIERTAS, vigencia__gte=timezone.localdate())),
        contratado=_sumar(confirmados, 'precio_total'),
        pagado=_sumar(pagos, 'monto', por='evento__cliente'),
        proximo=Subquery(vigentes.filter(fecha_fin_evento__gte=ahora).order_by('fecha_inicio_evento').values('fecha_inicio_evento')[:1]),
        ultimo=Subquery(vigentes.filter(fecha_fin_evento__lt=ahora).order_by('-fecha_inicio_evento').values('fecha_inicio_evento')[:1]),
    ).annotate(saldo=ExpressionWrapper(F('contratado') - F('pagado'), output_field=DINERO))


def resumen_de(cliente_id, usuario):
    """Un cliente con su resumen (para mostrarlo junto a su evento o cotización); None si no hay."""
    if not cliente_id:
        return None
    return con_resumen(Cliente.objects.visibles_para(usuario).filter(pk=cliente_id), usuario).first()


def para_formulario(usuario, limite=500):
    """Los clientes para elegir en el formulario de evento o de cotización (los de actividad más reciente primero)."""
    clientes = con_resumen(Cliente.objects.visibles_para(usuario), usuario).order_by('-actualizado')[:limite]
    return [{'id': c.pk, 'nombre': c.nombre, 'telefono': c.telefono, 'email': c.email,
             'tel': c.telefono_normalizado, 'eventos': c.n_eventos, 'cotizaciones': c.n_cotizaciones,
             'url': c.get_absolute_url()} for c in clientes]
