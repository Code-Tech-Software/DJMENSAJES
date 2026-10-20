import io
from datetime import datetime, timedelta

import qrcode
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Lower
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from apps.colaboradores.models import Colaborador
from apps.core.limites import LimitePlanMixin, bloquear_si_lleno
from apps.core.modulos import fotos_subidas, limite_fotos
from apps.core.mixins import AsignarAgenciaMixin, FormularioModalMixin, es_ajax, respuesta_ok
from apps.core.models import Ajustes
from apps.core.utils import generar_codigo, generar_token, qr_svg
from apps.envivo.models import Mensaje
from apps.envivo.servicios import notificar_evento, notificar_proyector
from apps.invitaciones.models import Invitado

from .asistente import crear_itinerario, eventos_cercanos
from .extras import activar, extras_de_conceptos, tiene_invitacion, valores_en_vivo
from .forms import ActividadForm, EnVivoForm, EventoForm, PagoForm, ProyectorForm
from .models import ActividadItinerario, ConceptoEvento, Evento, Pago, TipoEvento


# --- Utilidades de acceso -------------------------------------------------------------------

def eventos_de(usuario):
    return Evento.objects.visibles_para(usuario)


def obtener_evento(request, pk):
    return get_object_or_404(eventos_de(request.user).select_related('colaborador', 'banner', 'creado_por'), pk=pk)


def puede_eliminar(usuario, evento):
    return usuario.ve_todo or evento.creado_por_id == usuario.pk


# --- Listado, calendario y detalle -----------------------------------------------------------

CUANDO = {
    'proximos': ('Próximos', 'ph ph-calendar-dots'),
    'en_curso': ('En curso', 'ph ph-broadcast'),
    'pasados': ('Pasados', 'ph ph-clock-counter-clockwise'),
    'todos': ('Todos', 'ph ph-squares-four'),
}


@login_required
def lista(request):
    base = eventos_de(request.user)
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '')
    etapa = request.GET.get('etapa', '')
    colaborador = request.GET.get('colaborador', '')
    cuando = request.GET.get('cuando', 'proximos')
    if cuando not in CUANDO:
        cuando = 'proximos'

    filtrados = base
    if q:
        filtrados = filtrados.filter(Q(nombre_evento__icontains=q) | Q(lugar__icontains=q) | Q(cliente_nombre__icontains=q))
    if tipo:
        filtrados = filtrados.filter(tipo_evento=tipo)
    if etapa:
        filtrados = filtrados.filter(etapa=etapa)
    if colaborador and request.user.ve_todo:
        filtrados = filtrados.filter(colaborador_id=colaborador)

    ahora = timezone.now()
    conteos = {
        'proximos': filtrados.filter(fecha_inicio_evento__gt=ahora).count(),
        'en_curso': filtrados.filter(fecha_inicio_evento__lte=ahora, fecha_fin_evento__gte=ahora).count(),
        'pasados': filtrados.filter(fecha_fin_evento__lt=ahora).count(),
        'todos': filtrados.count(),
    }
    if cuando == 'proximos':
        filtrados = filtrados.proximos().order_by('fecha_inicio_evento')
    elif cuando == 'en_curso':
        filtrados = filtrados.en_curso().order_by('fecha_inicio_evento')
    elif cuando == 'pasados':
        filtrados = filtrados.pasados().order_by('-fecha_inicio_evento')
    else:
        filtrados = filtrados.order_by('-fecha_inicio_evento')

    filtrados = filtrados.select_related('colaborador', 'banner', 'invitacion').annotate(
        n_invitados=Count('invitados', distinct=True),
        pases=Sum('invitados__pases'),
        pases_confirmados=Sum('invitados__pases_confirmados', filter=Q(invitados__estado='confirmado')),
    )
    pagina = Paginator(filtrados, 12).get_page(request.GET.get('page'))
    query = request.GET.copy()
    query.pop('page', None)
    return render(request, 'eventos/lista.html', {
        'page_obj': pagina,
        'eventos': pagina.object_list,
        'q': q, 'tipo': tipo, 'etapa': etapa, 'colaborador': colaborador, 'cuando': cuando,
        'tipos': TipoEvento.choices,
        'etapas': Evento.Etapa.choices,
        'colaboradores': Colaborador.objects.filter(estado=True, agencia_id=request.user.agencia_id) if request.user.ve_todo else [],
        'opciones_cuando': [(k, v[0], v[1], conteos[k]) for k, v in CUANDO.items()],
        'query': query.urlencode(),
        'hay_filtros': any([q, tipo, etapa, colaborador]),
    })


@login_required
def calendario(request):
    return render(request, 'eventos/calendario.html', {'tipos': TipoEvento.choices})


@login_required
def api_calendario(request):
    eventos = eventos_de(request.user).select_related('colaborador')
    inicio = parse_datetime(request.GET.get('start', '') or '')
    fin = parse_datetime(request.GET.get('end', '') or '')
    if inicio:
        eventos = eventos.filter(fecha_fin_evento__gte=inicio)
    if fin:
        eventos = eventos.filter(fecha_inicio_evento__lte=fin)
    datos = [{
        'id': e.pk,
        'title': e.nombre_evento,
        'start': timezone.localtime(e.fecha_inicio_evento).isoformat(),
        'end': timezone.localtime(e.fecha_fin_evento).isoformat(),
        'classNames': ['em-ev', f'tipo-{e.tipo_evento}'] + ([] if e.estado and e.etapa != 'cancelado' else ['is-off']),
        'extendedProps': {
            'tipo': e.tipo_evento,
            'tipoNombre': e.tipo_corto,
            'lugar': e.lugar,
            'colaborador': e.colaborador.nombre if e.colaborador else '',
            'etapa': e.etapa,
            'url': reverse('eventos:vista_rapida', args=[e.pk]),
        },
    } for e in eventos]
    return JsonResponse(datos, safe=False)


def _resumen_mensajes(evento):
    mensajes = evento.mensajes.all()
    resumen = mensajes.aggregate(
        total=Count('id'),
        canciones=Count('id', filter=Q(tipo='cancion')),
        saludos=Count('id', filter=Q(tipo='saludo')),
        fotos=Count('id', filter=Q(tipo='foto')),
        fotos_album=Count('id', filter=Q(tipo='foto', estatus='atendido')),
        fotos_por_revisar=Count('id', filter=Q(tipo='foto', estatus='pendiente')),
        pendientes=Count('id', filter=Q(estatus='pendiente')),
        vip=Count('id', filter=Q(vip=True)),
    )
    top = (mensajes.filter(tipo='cancion').annotate(t=Lower('mensaje')).values('t')
           .annotate(n=Count('id')).order_by('-n')[:5])
    resumen['top'] = [{'titulo': t['t'].capitalize(), 'n': t['n']} for t in top]
    return resumen


def _resumen_en_vivo(evento):
    """'Reciben canciones, saludos y fotos · 2 min de espera · VIP' para la tarjeta de la experiencia en vivo."""
    envia = [nombre for activo, nombre in ((evento.permitir_canciones, 'canciones'), (evento.permitir_saludos, 'saludos'),
                                            (evento.permitir_fotos, 'fotos')) if activo]
    partes = [f'Reciben {", ".join(envia[:-1]) + " y " + envia[-1] if len(envia) > 1 else envia[0]}' if envia else 'Sin envíos de los invitados']
    if evento.cooldown:
        partes.append(f'{evento.cooldown:g} min de espera')
    if evento.password_vip:
        partes.append('con VIP')
    return ' · '.join(partes)


@login_required
def detalle(request, pk):
    evento = obtener_evento(request, pk)
    invitacion = getattr(evento, 'invitacion', None)
    url_invitados = request.build_absolute_uri(evento.url_invitados())
    return render(request, 'eventos/detalle.html', {
        'evento': evento,
        'invitacion': invitacion,
        'rsvp': evento.invitados.resumen(),
        'mensajes_resumen': _resumen_mensajes(evento),
        'mensajes': evento.mensajes.all()[:60],
        'itinerario': evento.itinerario_en_orden(),
        'pagos': evento.pagos.select_related('registrado_por'),
        'url_invitados': url_invitados,
        'url_pantalla': request.build_absolute_uri(evento.url_pantalla()),
        'url_dj': request.build_absolute_uri(evento.url_dj()),
        'url_album': request.build_absolute_uri(evento.url_album()),
        'url_pantalla_fotos': request.build_absolute_uri(evento.url_pantalla_fotos()),
        'limite_fotos': limite_fotos(evento),
        'fotos_subidas': fotos_subidas(evento),
        'resumen_en_vivo': _resumen_en_vivo(evento),
        'qr': qr_svg(url_invitados) if evento.con_en_vivo else '',
        'puede_eliminar': puede_eliminar(request.user, evento),
    })


@login_required
def disponibilidad(request):
    """Para el formulario: qué otros eventos hay ese día o se cruzan con el horario elegido."""
    inicio, fin = parse_datetime(request.GET.get('inicio', '')), parse_datetime(request.GET.get('fin', ''))
    if inicio is None:
        return JsonResponse({'eventos': []})
    inicio = timezone.make_aware(inicio) if timezone.is_naive(inicio) else inicio
    fin = (timezone.make_aware(fin) if fin and timezone.is_naive(fin) else fin) or inicio + timedelta(hours=1)
    excepto = request.GET.get('excepto', '')
    return JsonResponse({'eventos': [{
        'nombre': e.nombre_evento, 'tipo': e.tipo_corto, 'icono': e.icono, 'lugar': e.lugar,
        'horario': f'{timezone.localtime(e.fecha_inicio_evento):%H:%M} a {timezone.localtime(e.fecha_fin_evento):%H:%M}',
        'dia': timezone.localtime(e.fecha_inicio_evento).date().isoformat(), 'cruza': cruza,
        'colaborador': str(e.colaborador) if e.colaborador_id else '',
    } for e, cruza in eventos_cercanos(request.user, inicio, fin, excepto=excepto if excepto.isdigit() else None)]})


@login_required
def vista_rapida(request, pk):
    evento = obtener_evento(request, pk)
    return render(request, 'eventos/partials/vista_rapida.html', {
        'evento': evento,
        'rsvp': evento.invitados.resumen(),
        'n_mensajes': evento.mensajes.count(),
    })


@login_required
def orden(request, pk):
    evento = obtener_evento(request, pk)
    return render(request, 'eventos/orden.html', {
        'evento': evento,
        'pagos': evento.pagos.all(),
        'itinerario': evento.itinerario_en_orden(),
        'folio': f'EP-{evento.pk:05d}',  # EP = EventPro
        'hoy': timezone.localdate(),
        'agencia': Ajustes.de(evento.agencia_id),
    })


@login_required
def qr_png(request, pk):
    evento = obtener_evento_en_vivo(request, pk)
    url = request.build_absolute_uri(evento.url_invitados())
    imagen = qrcode.make(url, box_size=16, border=2)
    buffer = io.BytesIO()
    imagen.save(buffer, format='PNG')
    respuesta = HttpResponse(buffer.getvalue(), content_type='image/png')
    respuesta['Content-Disposition'] = f'attachment; filename="qr-{evento.codigo}.png"'
    return respuesta


@login_required
def centro_envivo(request):
    ahora = timezone.now()
    eventos = eventos_de(request.user).vigentes().filter(con_en_vivo=True).select_related('colaborador', 'banner')
    en_curso = list(eventos.en_curso().order_by('fecha_inicio_evento'))
    hoy_fin = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=3), datetime.max.time()))
    siguientes = list(eventos.filter(fecha_inicio_evento__gt=ahora, fecha_inicio_evento__lte=hoy_fin).order_by('fecha_inicio_evento'))
    for e in en_curso + siguientes:
        e.n_mensajes = e.mensajes.count()
        e.n_pendientes = e.mensajes.filter(estatus='pendiente').count()
    recientes = Mensaje.objects.filter(evento__in=[e.pk for e in en_curso]).select_related('evento')[:12]
    return render(request, 'eventos/centro_envivo.html', {
        'en_curso': en_curso, 'siguientes': siguientes, 'recientes': recientes,
    })


# --- Crear / editar / acciones ----------------------------------------------------------------

class EventoFormMixin(LoginRequiredMixin, FormularioModalMixin):
    """El registro de eventos es una página completa (ya no un modal): todo a la vista, con resumen al lado."""
    model = Evento
    form_class = EventoForm
    template_modal = 'eventos/form_evento.html'
    icono = 'ph ph-sparkle'

    def get_template_names(self):
        return [self.template_modal]

    def get(self, request, *args, **kwargs):
        if es_ajax(request):  # algo todavía lo abre en un modal: se manda a la página
            if 'pk' in kwargs:
                self.get_object()  # antes, 404 si el evento no es suyo
            return JsonResponse({'ok': True, 'redirect': request.get_full_path()})
        return super().get(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['usuario'] = self.request.user
        kwargs['fecha'] = self.request.GET.get('fecha')
        return kwargs


class EventoCrear(LimitePlanMixin, AsignarAgenciaMixin, EventoFormMixin, CreateView):
    recurso_limitado = 'eventos'
    titulo = 'Nuevo evento'
    subtitulo = 'Llena lo que tengas a la mano; todo se puede completar después.'
    texto_boton = 'Crear evento'

    def form_valid(self, form):
        form.instance.agencia_id = self.request.user.agencia_id
        form.instance.creado_por = self.request.user
        if not self.request.user.ve_todo and self.request.user.colaborador_id:
            form.instance.colaborador_id = self.request.user.colaborador_id
        # La experiencia en vivo nace con los valores de los Ajustes (y activa solo si la agencia lo eligió)
        valores_en_vivo(form.instance)
        extras = []
        with transaction.atomic():
            self.object = form.save()
            extras += [f'{nombre.lower()} activada' for nombre in activar(self.object, extras_de_conceptos(self.object.conceptos.all()))]
            if form.cleaned_data.get('anticipo'):
                Pago.objects.create(evento=self.object, monto=form.cleaned_data['anticipo'], referencia='Anticipo',
                                    metodo=form.cleaned_data.get('anticipo_metodo') or Pago.Metodo.TRANSFERENCIA,
                                    registrado_por=self.request.user)
                extras.append('anticipo registrado')
            if form.cleaned_data.get('itinerario_base'):
                crear_itinerario(self.object)
                extras.append('itinerario sugerido')
        detalle = f' ({" e ".join(extras)})' if extras else ''
        return respuesta_ok(self.request, f'¡Listo! "{self.object.nombre_evento}" fue creado{detalle}.',
                            redirect=self.object.get_absolute_url())


class EventoEditar(EventoFormMixin, UpdateView):
    texto_boton = 'Guardar cambios'
    mensaje_exito = 'Evento actualizado.'

    def get_url_exito(self):
        return super().get_url_exito() or self.object.get_absolute_url()

    def get_queryset(self):
        return eventos_de(self.request.user)

    def get_titulo(self):
        return 'Editar evento'

    def get_subtitulo(self):
        return self.object.nombre_evento

    def get_mensaje_exito(self):
        activados = getattr(self, 'activados', [])
        return f'Evento actualizado · se activó {" y ".join(activados).lower()}.' if activados else self.mensaje_exito

    def form_valid(self, form):
        self.object = form.save()
        # Un servicio vendido que activa un extra (en vivo, invitación) lo activa al guardar
        self.activados = activar(self.object, extras_de_conceptos(self.object.conceptos.all()))
        return self.respuesta_exito()


def obtener_evento_en_vivo(request, pk):
    """El evento, solo si tiene activa la experiencia en vivo (sus pantallas, QR y proyector)."""
    evento = obtener_evento(request, pk)
    if not evento.con_en_vivo:
        raise Http404('Este evento no tiene la experiencia en vivo.')
    return evento


@login_required
@require_POST
def en_vivo_activar(request, pk):
    evento = obtener_evento(request, pk)
    if not evento.con_en_vivo:
        evento.con_en_vivo = True
        evento.save(update_fields=['con_en_vivo', 'actualizado'])
    return respuesta_ok(request, 'Experiencia en vivo activada: revisa cómo quieres que funcione.',
                        abrir=reverse('eventos:en_vivo', args=[evento.pk]))


@login_required
@require_POST
def en_vivo_desactivar(request, pk):
    evento = obtener_evento(request, pk)
    if evento.con_en_vivo:
        evento.con_en_vivo = False
        evento.save(update_fields=['con_en_vivo', 'actualizado'])
        notificar_evento(evento)
    return respuesta_ok(request, 'Experiencia en vivo desactivada. Sus mensajes y fotos se conservan por si la vuelves a activar.')


class EnVivoEditar(LoginRequiredMixin, FormularioModalMixin, UpdateView):
    """Cómo funciona la experiencia en vivo de un evento: fondo, interacción, qué envían los invitados y proyector."""
    model = Evento
    form_class = EnVivoForm
    template_modal = 'eventos/partials/form_en_vivo.html'
    titulo = 'Experiencia en vivo'
    icono = 'ph ph-broadcast'
    tamano = 'lg'
    mensaje_exito = 'Experiencia en vivo actualizada.'

    def get_queryset(self):
        return eventos_de(self.request.user).filter(con_en_vivo=True)

    def get_subtitulo(self):
        return self.object.nombre_evento

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'usuario': self.request.user}

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        if 'estado' in form.changed_data:
            notificar_evento(self.object)
        if {'pantalla_contenido', 'pantalla_qr', 'moderar_pantalla', 'banner'} & set(form.changed_data):
            notificar_proyector(self.object)
        return respuesta


class ProyectorEditar(LoginRequiredMixin, FormularioModalMixin, UpdateView):
    """Qué se muestra en el proyector y de qué tamaño va el QR; se aplica al instante."""
    model = Evento
    form_class = ProyectorForm
    template_modal = 'eventos/partials/form_proyector.html'
    titulo = 'Pantalla del proyector'
    subtitulo = 'Elige qué se proyecta y cómo se ve el código QR.'
    icono = 'ph ph-projector-screen'
    tamano = 'lg'
    texto_boton = 'Aplicar'
    mensaje_exito = 'Proyector actualizado.'

    def get_queryset(self):
        return eventos_de(self.request.user).filter(con_en_vivo=True)

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        notificar_proyector(self.object)
        return respuesta


@login_required
@require_POST
def eliminar(request, pk):
    evento = obtener_evento(request, pk)
    if not puede_eliminar(request.user, evento):
        raise PermissionDenied
    nombre = evento.nombre_evento
    evento.delete()
    return respuesta_ok(request, f'Se eliminó "{nombre}".', redirect=reverse('eventos:lista'))


@login_required
@require_POST
def duplicar(request, pk):
    original = obtener_evento(request, pk)
    bloqueo = bloquear_si_lleno(request, 'eventos')  # la copia cuenta como evento nuevo del mes
    if bloqueo is not None:
        return bloqueo
    actividades = list(original.itinerario.all())
    conceptos = list(original.conceptos.all())
    copia = original
    copia.pk = None
    copia._state.adding = True
    copia.nombre_evento = f'{original.nombre_evento} (copia)'[:200]
    copia.codigo = generar_codigo(7)
    copia.token_dj = generar_token(18)
    copia.etapa = Evento.Etapa.COTIZACION
    copia.creado_por = request.user
    copia.creado = timezone.now()
    copia.save()
    ActividadItinerario.objects.bulk_create([
        ActividadItinerario(evento=copia, hora=a.hora, titulo=a.titulo, descripcion=a.descripcion, icono=a.icono)
        for a in actividades
    ])
    ConceptoEvento.objects.bulk_create([
        ConceptoEvento(evento=copia, servicio_id=c.servicio_id, paquete_id=c.paquete_id, descripcion=c.descripcion,
                       detalle=c.detalle, cantidad=c.cantidad, unidad=c.unidad, precio_unitario=c.precio_unitario, orden=c.orden)
        for c in conceptos
    ])
    destino = reverse('eventos:editar', args=[copia.pk])
    return respuesta_ok(request, 'Evento duplicado. Ajusta la fecha y los datos.', redirect=destino)


@login_required
@require_POST
def alternar_estado(request, pk):
    evento = obtener_evento_en_vivo(request, pk)
    evento.estado = not evento.estado
    evento.save(update_fields=['estado', 'actualizado'])
    notificar_evento(evento)
    texto = 'La interacción en vivo está activa.' if evento.estado else 'La interacción en vivo está pausada.'
    if es_ajax(request) and request.GET.get('silencioso'):
        return JsonResponse({'ok': True, 'estado': evento.estado, 'message': texto})
    return respuesta_ok(request, texto)


# --- Itinerario y pagos -----------------------------------------------------------------------

class HijoEventoMixin(LoginRequiredMixin, FormularioModalMixin):
    """Formularios de objetos que cuelgan de un evento visible para el usuario."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if 'evento_pk' in kwargs:
            self.evento = obtener_evento(request, kwargs['evento_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_subtitulo(self):
        return self.evento.nombre_evento


class ActividadCrear(HijoEventoMixin, CreateView):
    form_class = ActividadForm
    template_modal = 'eventos/partials/form_actividad.html'
    titulo = 'Agregar al itinerario'
    icono = 'ph ph-clock'
    texto_boton = 'Agregar'
    mensaje_exito = 'Actividad agregada al itinerario.'

    def form_valid(self, form):
        form.instance.evento = self.evento
        return super().form_valid(form)


class ActividadEditar(HijoEventoMixin, UpdateView):
    form_class = ActividadForm
    template_modal = 'eventos/partials/form_actividad.html'
    titulo = 'Editar actividad'
    icono = 'ph ph-clock'
    mensaje_exito = 'Itinerario actualizado.'

    def get_queryset(self):
        return ActividadItinerario.objects.filter(evento__in=eventos_de(self.request.user))

    def get_subtitulo(self):
        return self.object.evento.nombre_evento


@login_required
@require_POST
def actividad_eliminar(request, pk):
    actividad = get_object_or_404(ActividadItinerario, pk=pk, evento__in=eventos_de(request.user))
    actividad.delete()
    return respuesta_ok(request, 'Actividad eliminada.')


class PagoCrear(HijoEventoMixin, CreateView):
    form_class = PagoForm
    template_modal = 'eventos/partials/form_pago.html'
    titulo = 'Registrar pago'
    icono = 'ph ph-hand-coins'
    tamano = 'sm'
    texto_boton = 'Registrar'
    mensaje_exito = 'Pago registrado.'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['evento'] = self.evento
        return contexto

    def form_valid(self, form):
        form.instance.evento = self.evento
        form.instance.registrado_por = self.request.user
        return super().form_valid(form)


@login_required
@require_POST
def pago_eliminar(request, pk):
    pago = get_object_or_404(Pago, pk=pk, evento__in=eventos_de(request.user))
    pago.delete()
    return respuesta_ok(request, 'Pago eliminado.')
