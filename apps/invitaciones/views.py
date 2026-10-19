import calendar
import csv
from datetime import timedelta, timezone as dt_timezone
from urllib.parse import quote, urlencode

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, FormView, UpdateView

from apps.core.mixins import FormularioModalMixin, respuesta_ok
from apps.core.marca import Marca
from apps.core.modulos import tiene
from apps.core.models import Ajustes
from apps.core.utils import generar_token, qr_svg, slug_unico
from apps.eventos.models import Evento
from apps.eventos.views import eventos_de, obtener_evento

from .forms import ImportarInvitadosForm, InvitadoForm, RSVPAbiertoForm, RSVPForm
from .models import Invitacion, Invitado, Ubicacion

PLANTILLA_SUGERIDA = {
    'boda': 'elegante', 'aniversario': 'elegante', 'quinse': 'jardin', 'bautizo': 'jardin',
    'cumple': 'fiesta', 'fiesta': 'fiesta', 'graduacion': 'fiesta',
}


def obtener_invitacion(evento):
    """Devuelve la invitación del evento; la crea con valores sugeridos si no existe."""
    try:
        return evento.invitacion
    except Invitacion.DoesNotExist:
        ajustes = Ajustes.de(evento.agencia_id)
        plantilla = ajustes.plantilla or PLANTILLA_SUGERIDA.get(evento.tipo_evento, 'moderna')
        invitacion = Invitacion.objects.create(
            evento=evento,
            slug=slug_unico(evento.nombre_evento, Invitacion),
            plantilla=plantilla,
            color_principal=Invitacion.COLORES_PLANTILLA[plantilla],
            fecha_limite_rsvp=timezone.localdate(evento.fecha_inicio_evento) - timedelta(days=ajustes.dias_limite_rsvp),
        )
        if evento.lugar:
            Ubicacion.objects.create(
                invitacion=invitacion, tipo=Ubicacion.Tipo.RECEPCION, lugar=evento.lugar,
                direccion=evento.direccion, url_mapa=evento.url_mapa,
                hora=timezone.localtime(evento.fecha_inicio_evento).time(),
            )
        return invitacion


def mensaje_whatsapp(request, invitado, invitacion):
    url = request.build_absolute_uri(invitado.get_absolute_url())
    # Sin emojis: en algunos celulares llegan como "�"
    texto = (f'¡Hola {invitado.nombre}!\n'
             f'Con mucho cariño te compartimos la invitación: {invitacion.titulo_visible} · {invitacion.nombres_visibles}.\n'
             f'Ábrela y confirma tu asistencia aquí: {url}')
    destino = f'https://wa.me/{invitado.whatsapp_numero}' if invitado.whatsapp_numero else 'https://wa.me/'
    return f'{destino}?text={quote(texto)}'


# --- Panel interno -----------------------------------------------------------------------------

@login_required
def indice(request):
    ver_pasados = request.GET.get('pasados') == '1'
    eventos = eventos_de(request.user).vigentes().select_related('invitacion', 'banner')
    eventos = eventos.order_by('-fecha_inicio_evento') if ver_pasados else eventos.filter(fecha_fin_evento__gte=timezone.now()).order_by('fecha_inicio_evento')
    eventos = eventos.annotate(
        n_invitados=Count('invitados'),
        pases=Sum('invitados__pases'),
        confirmados=Sum('invitados__pases_confirmados', filter=Q(invitados__estado='confirmado')),
        vistos=Count('invitados', filter=Q(invitados__vista_en__isnull=False)),
    )
    return render(request, 'invitaciones/indice.html', {'eventos': eventos, 'ver_pasados': ver_pasados})


def lista_invitados(request, evento, invitacion, *, token=None):
    """
    Lista filtrada de invitados con las rutas de cada acción. La comparten el panel del equipo y el de
    los anfitriones (token = su enlace privado), que usan la misma tabla con rutas distintas.
    """
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    grupo = request.GET.get('grupo', '')

    invitados = evento.invitados.all()
    if q:
        invitados = invitados.filter(Q(nombre__icontains=q) | Q(telefono__icontains=q) | Q(mesa__iexact=q))
    if estado == 'sin_enviar':
        invitados = invitados.filter(enviada_en__isnull=True)
    elif estado == 'vista':
        invitados = invitados.filter(vista_en__isnull=False, estado='pendiente')
    elif estado:
        invitados = invitados.filter(estado=estado)
    if grupo:
        invitados = invitados.filter(grupo=grupo)

    espacio, base = ('anfitriones', [token]) if token else ('invitaciones', [])
    invitados = list(invitados)
    for invitado in invitados:
        invitado.wa_url = mensaje_whatsapp(request, invitado, invitacion)
        args = base + [invitado.pk]
        invitado.url_editar = reverse(f'{espacio}:invitado_editar', args=args)
        invitado.url_eliminar = reverse(f'{espacio}:invitado_eliminar', args=args)
        invitado.url_enviada = reverse(f'{espacio}:marcar_enviada', args=args)

    args = [token] if token else [evento.pk]
    return {
        'invitados': invitados,
        'resumen': evento.invitados.resumen(),
        'grupos': evento.invitados.exclude(grupo='').values_list('grupo', flat=True).distinct().order_by('grupo'),
        'q': q, 'estado': estado, 'grupo': grupo,
        'url_crear': reverse(f'{espacio}:invitado_crear', args=args),
        'url_importar': reverse(f'{espacio}:importar', args=args),
        'url_exportar': reverse(f'{espacio}:exportar', args=args),
        'url_entrada': '' if token else reverse('invitaciones:checkin', args=args),
    }


@login_required
def panel(request, pk):
    evento = obtener_evento(request, pk)
    invitacion = obtener_invitacion(evento)
    contexto = lista_invitados(request, evento, invitacion)
    contexto.update({
        'evento': evento,
        'invitacion': invitacion,
        'url_publica': request.build_absolute_uri(invitacion.get_absolute_url()),
        'plantillas': Invitacion.Plantilla.choices,
    })
    if invitacion.token_anfitriones:
        url = request.build_absolute_uri(invitacion.url_anfitriones())
        texto = (f'¡Hola! Este es el enlace para administrar la lista de invitados de {invitacion.nombres_visibles}:\n{url}\n'
                 'Desde ahí pueden agregar a sus invitados, enviarles su invitación por WhatsApp y ver quién confirmó.')
        contexto.update({'url_anfitriones': url, 'wa_anfitriones': f'https://wa.me/?text={quote(texto)}'})
    return render(request, 'invitaciones/panel.html', contexto)


@login_required
@require_POST
def cambiar_plantilla(request, pk):
    invitacion = obtener_invitacion(obtener_evento(request, pk))
    plantilla = request.POST.get('plantilla')
    if plantilla in Invitacion.Plantilla.values:
        invitacion.plantilla = plantilla
        invitacion.color_principal = Invitacion.COLORES_PLANTILLA[plantilla]
        invitacion.save(update_fields=['plantilla', 'color_principal', 'actualizado'])
    return JsonResponse({'ok': True, 'plantilla': invitacion.plantilla})


@login_required
@require_POST
def publicar(request, pk):
    invitacion = obtener_invitacion(obtener_evento(request, pk))
    invitacion.publicada = not invitacion.publicada
    invitacion.save(update_fields=['publicada', 'actualizado'])
    return respuesta_ok(request, '¡Invitación publicada! Ya puedes compartirla.' if invitacion.publicada
                        else 'La invitación volvió a borrador.')


@login_required
@require_POST
def enlace_anfitriones(request, pk, accion):
    """Crea, cambia o desactiva el enlace privado con el que los anfitriones administran su lista."""
    invitacion = obtener_invitacion(obtener_evento(request, pk))
    if accion == 'desactivar':
        invitacion.token_anfitriones = None
        mensaje = 'Enlace desactivado: los anfitriones ya no pueden entrar.'
    elif accion == 'regenerar' or not invitacion.token_anfitriones:
        mensaje = ('Se creó un enlace nuevo; el anterior dejó de funcionar.' if invitacion.token_anfitriones
                   else 'Enlace creado. Compártelo con los anfitriones.')
        invitacion.token_anfitriones = generar_token(18)
    else:
        return respuesta_ok(request)
    invitacion.save(update_fields=['token_anfitriones', 'actualizado'])
    return respuesta_ok(request, mensaje)


# Formularios de invitados: los usan el equipo (abajo) y los anfitriones (anfitriones.py); cada uno
# define get_evento() y desde dónde se puede editar.

class InvitadoFormMixin(FormularioModalMixin):
    model = Invitado
    form_class = InvitadoForm
    template_modal = 'invitaciones/partials/form_invitado.html'
    icono = 'ph ph-user-list'

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['grupos'] = self.get_evento().invitados.exclude(grupo='').values_list('grupo', flat=True).distinct()
        return contexto


class InvitadoCrearBase(InvitadoFormMixin, CreateView):
    titulo = 'Agregar invitado'
    texto_boton = 'Agregar'
    mensaje_exito = 'Invitado agregado.'

    def get_subtitulo(self):
        return self.get_evento().nombre_evento

    def form_valid(self, form):
        form.instance.evento = self.get_evento()
        obtener_invitacion(form.instance.evento)
        if 'otro' in self.request.POST:
            form.save()
            return respuesta_ok(self.request, f'{form.instance.nombre} agregado.', recargar=False, abrir=self.request.path)
        return super().form_valid(form)


class InvitadoEditarBase(InvitadoFormMixin, UpdateView):
    titulo = 'Editar invitado'
    mensaje_exito = 'Invitado actualizado.'

    def get_evento(self):
        return self.object.evento

    def get_subtitulo(self):
        return self.object.nombre

    def form_valid(self, form):
        if 'estado' in form.changed_data:
            form.instance.respondido_en = timezone.now() if form.instance.estado != Invitado.Estado.PENDIENTE else None
        return super().form_valid(form)


class ImportarInvitadosBase(FormularioModalMixin, FormView):
    form_class = ImportarInvitadosForm
    template_modal = 'invitaciones/partials/form_importar.html'
    titulo = 'Importar lista de invitados'
    subtitulo = 'Pega tu lista desde Excel, WhatsApp o notas.'
    icono = 'ph ph-clipboard-text'
    tamano = 'lg'
    texto_boton = 'Importar'

    def form_valid(self, form):
        evento = self.get_evento()
        obtener_invitacion(evento)
        grupo_general = form.cleaned_data.get('grupo', '')
        nuevos = [Invitado(evento=evento, nombre=f['nombre'], pases=f['pases'], telefono=f['telefono'],
                           grupo=f['grupo'] or grupo_general) for f in form.cleaned_data['lista']]
        Invitado.objects.bulk_create(nuevos)
        self.mensaje_exito = f'Se importaron {len(nuevos)} invitaciones ({sum(i.pases for i in nuevos)} pases).'
        return self.respuesta_exito()


class InvitadoCrear(LoginRequiredMixin, InvitadoCrearBase):
    def get_evento(self):
        if not hasattr(self, '_evento'):
            self._evento = obtener_evento(self.request, self.kwargs['pk'])
        return self._evento


class InvitadoEditar(LoginRequiredMixin, InvitadoEditarBase):
    def get_queryset(self):
        return Invitado.objects.filter(evento__in=eventos_de(self.request.user))


class ImportarInvitados(LoginRequiredMixin, ImportarInvitadosBase):
    def get_evento(self):
        return obtener_evento(self.request, self.kwargs['pk'])


@login_required
@require_POST
def invitado_eliminar(request, pk):
    invitado = get_object_or_404(Invitado, pk=pk, evento__in=eventos_de(request.user))
    invitado.delete()
    return respuesta_ok(request, f'Se quitó a {invitado.nombre} de la lista.')


@login_required
def exportar(request, pk):
    evento = obtener_evento(request, pk)
    return csv_invitados(request, evento, obtener_invitacion(evento))


def csv_invitados(request, evento, invitacion):
    respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
    respuesta['Content-Disposition'] = f'attachment; filename="invitados-{invitacion.slug}.csv"'
    respuesta.write('\ufeff')  # BOM para que Excel respete los acentos
    escritor = csv.writer(respuesta)
    escritor.writerow(['Nombre', 'Grupo', 'Mesa', 'Pases', 'Respuesta', 'Pases confirmados', 'WhatsApp',
                       'Correo', 'Mensaje', 'Vio invitación', 'Llegó', 'Enlace'])
    for i in evento.invitados.all():
        escritor.writerow([
            i.nombre, i.grupo, i.mesa, i.pases, i.get_estado_display(), i.pases_confirmados, i.telefono, i.email,
            i.mensaje, 'Sí' if i.vista_en else 'No',
            timezone.localtime(i.check_in_en).strftime('%H:%M') if i.check_in_en else '',
            request.build_absolute_uri(i.get_absolute_url()),
        ])
    return respuesta


@login_required
@require_POST
def marcar_enviada(request, pk):
    return registrar_envio(get_object_or_404(Invitado, pk=pk, evento__in=eventos_de(request.user)))


def registrar_envio(invitado):
    if not invitado.enviada_en:
        invitado.enviada_en = timezone.now()
        invitado.save(update_fields=['enviada_en'])
    return JsonResponse({'ok': True})


# --- Registro de entrada (check-in) -------------------------------------------------------------

@login_required
def checkin(request, pk):
    evento = obtener_evento(request, pk)
    return render(request, 'invitaciones/checkin.html', {
        'evento': evento,
        'invitados': evento.invitados.exclude(estado=Invitado.Estado.RECHAZADO),
        'resumen': evento.invitados.resumen(),
    })


@login_required
@require_POST
def checkin_marcar(request, pk):
    invitado = get_object_or_404(Invitado, pk=pk, evento__in=eventos_de(request.user))
    if invitado.check_in_en and request.POST.get('deshacer'):
        invitado.check_in_en = None
    elif not invitado.check_in_en:
        invitado.check_in_en = timezone.now()
        if invitado.estado != Invitado.Estado.CONFIRMADO:
            invitado.estado = Invitado.Estado.CONFIRMADO
            invitado.pases_confirmados = invitado.pases
    invitado.save()
    resumen = invitado.evento.invitados.resumen()
    return JsonResponse({
        'ok': True,
        'llego': bool(invitado.check_in_en),
        'hora': timezone.localtime(invitado.check_in_en).strftime('%H:%M') if invitado.check_in_en else '',
        'llegaron': resumen['llegaron'] or 0,
        'pases_llegaron': resumen['pases_llegaron'] or 0,
    })


@login_required
def checkin_escaneo(request, token):
    """Destino del QR del pase: el staff lo escanea con la cámara del celular."""
    invitado = get_object_or_404(Invitado.objects.select_related('evento'), token=token)
    if not eventos_de(request.user).filter(pk=invitado.evento_id).exists():
        raise Http404
    recien = False
    if request.method == 'POST' and not invitado.check_in_en:
        invitado.check_in_en = timezone.now()
        if invitado.estado != Invitado.Estado.CONFIRMADO:
            invitado.estado = Invitado.Estado.CONFIRMADO
            invitado.pases_confirmados = invitado.pases
        invitado.save()
        recien = True
    return render(request, 'invitaciones/checkin_escaneo.html', {'invitado': invitado, 'evento': invitado.evento, 'recien': recien})


# --- Invitación pública -------------------------------------------------------------------------

def _contexto_publico(request, invitacion, invitado=None):
    evento = invitacion.evento
    inicio = timezone.localtime(evento.fecha_inicio_evento)
    fin = timezone.localtime(evento.fecha_fin_evento)
    google = 'https://calendar.google.com/calendar/render?' + urlencode({
        'action': 'TEMPLATE',
        'text': f'{invitacion.titulo_visible} · {invitacion.nombres_visibles}',
        'dates': f"{evento.fecha_inicio_evento.astimezone(dt_timezone.utc):%Y%m%dT%H%M%SZ}/{evento.fecha_fin_evento.astimezone(dt_timezone.utc):%Y%m%dT%H%M%SZ}",
        'location': ', '.join(x for x in [evento.lugar, evento.direccion] if x),
        'details': request.build_absolute_uri(invitado.get_absolute_url() if invitado else invitacion.get_absolute_url()),
    })
    cerrado = invitacion.rsvp_vencido or evento.fecha_inicio_evento < timezone.now()
    semanas = calendar.Calendar(firstweekday=0).monthdayscalendar(inicio.year, inicio.month)
    contexto = {
        'invitacion': invitacion,
        'evento': evento,
        'invitado': invitado,
        'inicio': inicio,
        'fin': fin,
        'itinerario': evento.itinerario.all(),
        'ubicaciones': invitacion.ubicaciones.all(),
        'menciones': invitacion.menciones.all(),
        'fotos': invitacion.fotos.all(),
        'fotos_urls': [f.imagen.url for f in invitacion.fotos.all()],
        'semanas': semanas,
        'colaborador': evento.colaborador,
        'google_calendar': google,
        'rsvp_cerrado': cerrado,
        'es_equipo': request.user.is_authenticated and eventos_de(request.user).filter(pk=evento.pk).exists(),
        'es_anfitrion': es_anfitrion(request, invitacion),
        'ajustes': Ajustes.de(evento.agencia_id),
        'marca': Marca(evento),
    }
    imagen = invitacion.imagen_portada
    if imagen:
        try:
            url_imagen = imagen.url
            contexto['og_imagen'] = url_imagen if url_imagen.startswith('http') else request.build_absolute_uri(url_imagen)
        except Exception:  # almacenamiento no disponible
            contexto['og_imagen'] = ''
    contexto['preview'] = request.GET.get('preview') == '1'
    if invitado and invitado.estado == Invitado.Estado.CONFIRMADO:
        contexto['pase_qr'] = qr_svg(request.build_absolute_uri(reverse('invitaciones:checkin_escaneo', args=[invitado.token])))
    return contexto


def clave_anfitrion(invitacion):
    return f'anfitrion_{invitacion.pk}'


def es_anfitrion(request, invitacion):
    """Quien abrió el panel de los anfitriones en este navegador (con el enlace vigente)."""
    token = invitacion.token_anfitriones
    return bool(token) and request.session.get(clave_anfitrion(invitacion)) == token


def _verificar_publicada(request, invitacion):
    if not tiene(invitacion.evento.agencia, 'invitaciones'):
        return False  # el plan de la agencia ya no incluye invitaciones digitales
    if invitacion.publicada or es_anfitrion(request, invitacion):
        return True
    return request.user.is_authenticated and eventos_de(request.user).filter(pk=invitacion.evento_id).exists()


def invitacion_general(request, slug):
    invitacion = get_object_or_404(Invitacion.objects.select_related('evento__colaborador', 'evento__banner'), slug=slug)
    if not _verificar_publicada(request, invitacion):
        return render(request, 'invitaciones/publica/no_disponible.html', {'invitacion': invitacion}, status=404)
    clave = f'inv_vista_{invitacion.pk}'
    if not request.session.get(clave) and not request.user.is_authenticated and not es_anfitrion(request, invitacion):
        request.session[clave] = True
        Invitacion.objects.filter(pk=invitacion.pk).update(visitas=F('visitas') + 1)
    contexto = _contexto_publico(request, invitacion)
    contexto['form'] = RSVPAbiertoForm()
    return render(request, 'invitaciones/publica/invitacion.html', contexto)


def invitacion_personal(request, slug, token):
    invitacion = get_object_or_404(Invitacion.objects.select_related('evento__colaborador', 'evento__banner'), slug=slug)
    invitado = get_object_or_404(Invitado, token=token, evento_id=invitacion.evento_id)
    if not _verificar_publicada(request, invitacion):
        return render(request, 'invitaciones/publica/no_disponible.html', {'invitacion': invitacion}, status=404)
    contexto = _contexto_publico(request, invitacion, invitado)
    # Ni el equipo ni los anfitriones cuentan como "la vio" al revisar el enlace de alguien
    if not contexto['es_equipo'] and not contexto['es_anfitrion'] and not invitado.vista_en:
        invitado.vista_en = timezone.now()
        invitado.save(update_fields=['vista_en'])
        Invitacion.objects.filter(pk=invitacion.pk).update(visitas=F('visitas') + 1)
    contexto['form'] = RSVPForm(maximo=invitado.pases)
    contexto['respondio'] = request.GET.get('respondio')
    return render(request, 'invitaciones/publica/invitacion.html', contexto)


@require_POST
def rsvp(request, slug, token):
    invitacion = get_object_or_404(Invitacion, slug=slug)
    invitado = get_object_or_404(Invitado, token=token, evento_id=invitacion.evento_id)
    if not tiene(invitacion.evento.agencia, 'invitaciones'):
        raise Http404
    url = invitado.get_absolute_url()
    if invitacion.rsvp_vencido or invitacion.evento.fecha_inicio_evento < timezone.now():
        return redirect(url + '#confirmar')
    form = RSVPForm(request.POST, maximo=invitado.pases)
    if form.is_valid():
        asistira = form.cleaned_data['asistira'] == 'si'
        invitado.estado = Invitado.Estado.CONFIRMADO if asistira else Invitado.Estado.RECHAZADO
        invitado.pases_confirmados = form.cleaned_data['pases'] if asistira else 0
        invitado.mensaje = form.cleaned_data.get('mensaje', '')
        invitado.respondido_en = timezone.now()
        invitado.save()
        return redirect(f"{url}?respondio={'si' if asistira else 'no'}#confirmar")
    return redirect(url + '#confirmar')


@require_POST
def rsvp_abierto(request, slug):
    invitacion = get_object_or_404(Invitacion, slug=slug, rsvp_abierto=True)
    if not _verificar_publicada(request, invitacion):
        raise Http404
    if invitacion.rsvp_vencido or invitacion.evento.fecha_inicio_evento < timezone.now():
        return redirect(invitacion.get_absolute_url() + '#confirmar')
    form = RSVPAbiertoForm(request.POST)
    if not form.is_valid():
        return redirect(invitacion.get_absolute_url() + '#confirmar')
    asistira = form.cleaned_data['asistira'] == 'si'
    pases = form.cleaned_data['pases'] if asistira else 1
    invitado = Invitado.objects.create(
        evento=invitacion.evento,
        nombre=form.cleaned_data['nombre'],
        telefono=form.cleaned_data.get('telefono', ''),
        pases=pases,
        pases_confirmados=pases if asistira else 0,
        estado=Invitado.Estado.CONFIRMADO if asistira else Invitado.Estado.RECHAZADO,
        mensaje=form.cleaned_data.get('mensaje', ''),
        origen=Invitado.Origen.PUBLICO,
        respondido_en=timezone.now(),
        vista_en=timezone.now(),
    )
    return redirect(f"{invitado.get_absolute_url()}?respondio={'si' if asistira else 'no'}#confirmar")


def calendario_ics(request, slug):
    invitacion = get_object_or_404(Invitacion.objects.select_related('evento'), slug=slug)
    if not tiene(invitacion.evento.agencia, 'invitaciones'):
        raise Http404
    evento = invitacion.evento
    formato = '%Y%m%dT%H%M%SZ'

    def limpiar(texto):
        return (texto or '').replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')

    contenido = '\r\n'.join([
        'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//EventPro//Invitaciones//ES', 'BEGIN:VEVENT',
        f'UID:evento-{evento.pk}@eventpro',
        f'DTSTAMP:{timezone.now().astimezone(dt_timezone.utc).strftime(formato)}',
        f'DTSTART:{evento.fecha_inicio_evento.astimezone(dt_timezone.utc).strftime(formato)}',
        f'DTEND:{evento.fecha_fin_evento.astimezone(dt_timezone.utc).strftime(formato)}',
        f'SUMMARY:{limpiar(invitacion.titulo_visible + " · " + invitacion.nombres_visibles)}',
        f"LOCATION:{limpiar(', '.join(x for x in [evento.lugar, evento.direccion] if x))}",
        f'URL:{request.build_absolute_uri(invitacion.get_absolute_url())}',
        'END:VEVENT', 'END:VCALENDAR', '',
    ])
    respuesta = HttpResponse(contenido, content_type='text/calendar; charset=utf-8')
    respuesta['Content-Disposition'] = f'attachment; filename="{invitacion.slug}.ics"'
    return respuesta
