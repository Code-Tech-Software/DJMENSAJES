import io
from datetime import datetime, timedelta

import qrcode
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import Lower
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from apps.colaboradores.models import Colaborador
from apps.core.mixins import FormularioModalMixin, es_ajax, respuesta_ok
from apps.core.utils import generar_codigo, generar_token, qr_svg
from apps.envivo.models import Mensaje
from apps.envivo.servicios import notificar_evento
from apps.invitaciones.models import Invitado

from .forms import ActividadForm, EventoForm, PagoForm
from .models import ActividadItinerario, Evento, Pago, TipoEvento


# --- Utilidades de acceso -------------------------------------------------------------------

def eventos_de(usuario):
    return Evento.objects.visibles_para(usuario)


def obtener_evento(request, pk):
    return get_object_or_404(eventos_de(request.user).select_related('colaborador', 'banner', 'creado_por'), pk=pk)


def puede_eliminar(usuario, evento):
    return usuario.ve_todo or evento.creado_por_id == usuario.pk


# --- Listado, calendario y detalle -----------------------------------------------------------

CUANDO = {
    'proximos': ('Próximos', 'ri-calendar-event-line'),
    'en_curso': ('En curso', 'ri-broadcast-line'),
    'pasados': ('Pasados', 'ri-history-line'),
    'todos': ('Todos', 'ri-apps-2-line'),
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
        'colaboradores': Colaborador.objects.filter(estado=True) if request.user.ve_todo else [],
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
        pendientes=Count('id', filter=Q(estatus='pendiente')),
        vip=Count('id', filter=Q(vip=True)),
    )
    top = (mensajes.filter(tipo='cancion').annotate(t=Lower('mensaje')).values('t')
           .annotate(n=Count('id')).order_by('-n')[:5])
    resumen['top'] = [{'titulo': t['t'].capitalize(), 'n': t['n']} for t in top]
    return resumen


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
        'itinerario': evento.itinerario.all(),
        'pagos': evento.pagos.select_related('registrado_por'),
        'url_invitados': url_invitados,
        'url_pantalla': request.build_absolute_uri(evento.url_pantalla()),
        'url_dj': request.build_absolute_uri(evento.url_dj()),
        'qr': qr_svg(url_invitados),
        'puede_eliminar': puede_eliminar(request.user, evento),
    })


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
        'itinerario': evento.itinerario.all(),
        'folio': f'EM-{evento.pk:05d}',
        'hoy': timezone.localdate(),
    })


@login_required
def qr_png(request, pk):
    evento = obtener_evento(request, pk)
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
    eventos = eventos_de(request.user).vigentes().select_related('colaborador', 'banner')
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
    model = Evento
    form_class = EventoForm
    template_modal = 'eventos/partials/form_evento.html'
    tamano = 'lg'
    icono = 'ri-sparkling-2-line'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['usuario'] = self.request.user
        kwargs['fecha'] = self.request.GET.get('fecha')
        return kwargs


class EventoCrear(EventoFormMixin, CreateView):
    titulo = 'Nuevo evento'
    subtitulo = 'Te guiamos paso a paso. Podrás editar todo después.'
    texto_boton = 'Crear evento'

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        if not self.request.user.ve_todo and self.request.user.colaborador_id:
            form.instance.colaborador_id = self.request.user.colaborador_id
        self.object = form.save()
        return respuesta_ok(self.request, f'¡Listo! "{self.object.nombre_evento}" fue creado.',
                            redirect=self.object.get_absolute_url())


class EventoEditar(EventoFormMixin, UpdateView):
    texto_boton = 'Guardar cambios'
    mensaje_exito = 'Evento actualizado.'

    def get_queryset(self):
        return eventos_de(self.request.user)

    def get_titulo(self):
        return 'Editar evento'

    def get_subtitulo(self):
        return self.object.nombre_evento


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
    actividades = list(original.itinerario.all())
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
    destino = f"{copia.get_absolute_url()}?abrir={reverse('eventos:editar', args=[copia.pk])}"
    return respuesta_ok(request, 'Evento duplicado. Ajusta la fecha y los datos.', redirect=destino)


@login_required
@require_POST
def alternar_estado(request, pk):
    evento = obtener_evento(request, pk)
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
    icono = 'ri-time-line'
    texto_boton = 'Agregar'
    mensaje_exito = 'Actividad agregada al itinerario.'

    def form_valid(self, form):
        form.instance.evento = self.evento
        return super().form_valid(form)


class ActividadEditar(HijoEventoMixin, UpdateView):
    form_class = ActividadForm
    template_modal = 'eventos/partials/form_actividad.html'
    titulo = 'Editar actividad'
    icono = 'ri-time-line'
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
    icono = 'ri-hand-coin-line'
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
