"""
Editor de invitaciones: página con vista previa en vivo, guardado automático y
administración de lugares, personas especiales y galería.
"""
from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from apps.core.mixins import FormularioModalMixin, respuesta_ok
from apps.eventos.views import eventos_de, obtener_evento

from . import contenido
from .forms import MAX_IMAGEN_MB, InvitacionForm, MencionForm, UbicacionForm, validar_peso
from .models import FotoInvitacion, Invitacion, Mencion, Ubicacion
from .views import obtener_invitacion

MAX_FOTOS = 24


def _invitacion_de(request, pk):
    return obtener_invitacion(obtener_evento(request, pk))


def _contexto_listas(invitacion):
    return {
        'ubicaciones': invitacion.ubicaciones.all(),
        'menciones': invitacion.menciones.all(),
        'fotos': invitacion.fotos.all(),
        'max_fotos': MAX_FOTOS,
    }


@login_required
def editor(request, pk):
    evento = obtener_evento(request, pk)
    invitacion = obtener_invitacion(evento)
    contexto = {
        'evento': evento,
        'invitacion': invitacion,
        'form': InvitacionForm(instance=invitacion),
        'plantillas': contenido.PLANTILLAS,
        'paletas': Invitacion.PALETAS,
        'colores_plantilla': Invitacion.COLORES_PLANTILLA,
        'frases': contenido.frases_para(evento.tipo_evento),
        'avisos': contenido.AVISOS,
        'url_publica': request.build_absolute_uri(invitacion.get_absolute_url()),
        **_contexto_listas(invitacion),
    }
    # Sugerencia de encabezado según el tipo de evento (se muestra como texto de ejemplo)
    contexto['titulo_sugerido'] = Invitacion(evento=evento).titulo_visible
    return render(request, 'invitaciones/editor/editor.html', contexto)


@login_required
@require_POST
def guardar(request, pk):
    """Guardado automático del editor. Responde qué cambió para refrescar la vista previa."""
    invitacion = _invitacion_de(request, pk)
    form = InvitacionForm(request.POST, request.FILES, instance=invitacion)
    if not form.is_valid():
        errores = {campo: [str(e) for e in lista] for campo, lista in form.errors.items()}
        return JsonResponse({'ok': False, 'errores': errores}, status=422)
    cambios = set(form.changed_data)
    form.save()
    return JsonResponse({
        'ok': True,
        'hora': timezone.localtime().strftime('%H:%M'),
        'publicada': invitacion.publicada,
        # La plantilla y los archivos cambian el contenido de la página: se recarga la vista previa
        'recargar': bool(cambios & {'plantilla', 'portada', 'musica'}),
        'portada': invitacion.portada.url if invitacion.portada else '',
        'musica': invitacion.musica.url if invitacion.musica else '',
    })


# --- Lugares y personas ------------------------------------------------------------------------

class HijoInvitacionMixin(LoginRequiredMixin, FormularioModalMixin):
    """Formularios en modal del editor. Al guardar no recargan la página: el editor
    refresca la lista y la vista previa."""
    seccion = ''
    tamano = 'lg'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if 'evento_pk' in kwargs:
            self.invitacion = _invitacion_de(request, kwargs['evento_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.model.objects.filter(invitacion__evento__in=eventos_de(self.request.user))

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto['sugerencias'] = Mencion.SUGERENCIAS
        return contexto

    def form_valid(self, form):
        if not form.instance.pk:
            form.instance.invitacion = self.invitacion
            ultimo = self.model.objects.filter(invitacion=self.invitacion).order_by('-orden').first()
            form.instance.orden = (ultimo.orden + 1) if ultimo else 0
        self.object = form.save()
        return respuesta_ok(self.request, self.get_mensaje_exito(), recargar=False,
                            refrescar=self.seccion, seccion=self.seccion)


class UbicacionCrear(HijoInvitacionMixin, CreateView):
    model = Ubicacion
    form_class = UbicacionForm
    template_modal = 'invitaciones/editor/form_ubicacion.html'
    titulo = 'Agregar lugar'
    subtitulo = 'Ceremonia, recepción, fiesta… con su hora y ubicación.'
    icono = 'ri-map-pin-add-line'
    texto_boton = 'Agregar lugar'
    mensaje_exito = 'Lugar agregado.'
    seccion = 'lugares'

    def get_initial(self):
        inicial = super().get_initial()
        if not self.invitacion.ubicaciones.exists():
            evento = self.invitacion.evento
            inicial.update({'lugar': evento.lugar, 'direccion': evento.direccion, 'url_mapa': evento.url_mapa,
                            'hora': timezone.localtime(evento.fecha_inicio_evento).time()})
        return inicial


class UbicacionEditar(HijoInvitacionMixin, UpdateView):
    model = Ubicacion
    form_class = UbicacionForm
    template_modal = 'invitaciones/editor/form_ubicacion.html'
    titulo = 'Editar lugar'
    icono = 'ri-map-pin-line'
    mensaje_exito = 'Lugar actualizado.'
    seccion = 'lugares'


class MencionCrear(HijoInvitacionMixin, CreateView):
    model = Mencion
    form_class = MencionForm
    template_modal = 'invitaciones/editor/form_mencion.html'
    titulo = 'Agregar personas especiales'
    subtitulo = 'Padres, padrinos, damas… cada grupo con su título.'
    icono = 'ri-hearts-line'
    tamano = ''
    texto_boton = 'Agregar'
    mensaje_exito = 'Agregado a la invitación.'
    seccion = 'personas'


class MencionEditar(HijoInvitacionMixin, UpdateView):
    model = Mencion
    form_class = MencionForm
    template_modal = 'invitaciones/editor/form_mencion.html'
    titulo = 'Editar personas especiales'
    icono = 'ri-hearts-line'
    tamano = ''
    mensaje_exito = 'Cambios guardados.'
    seccion = 'personas'


MODELOS = {'lugares': Ubicacion, 'personas': Mencion, 'galeria': FotoInvitacion}


def _objeto(request, seccion, pk):
    modelo = MODELOS[seccion]
    return get_object_or_404(modelo, pk=pk, invitacion__evento__in=eventos_de(request.user))


@login_required
@require_POST
def eliminar(request, seccion, pk):
    objeto = _objeto(request, seccion, pk)
    objeto.delete()
    textos = {'lugares': 'Lugar eliminado.', 'personas': 'Grupo eliminado.', 'galeria': 'Foto eliminada.'}
    return respuesta_ok(request, textos[seccion], recargar=False, refrescar=seccion, seccion=seccion)


@login_required
@require_POST
def mover(request, seccion, pk, direccion):
    objeto = _objeto(request, seccion, pk)
    hermanos = list(MODELOS[seccion].objects.filter(invitacion=objeto.invitacion))
    i = hermanos.index(objeto)
    j = i - 1 if direccion == 'arriba' else i + 1
    if 0 <= j < len(hermanos):
        hermanos[i], hermanos[j] = hermanos[j], hermanos[i]
    for orden, item in enumerate(hermanos):
        if item.orden != orden:
            item.orden = orden
            item.save(update_fields=['orden'])
    return respuesta_ok(request, '', recargar=False, refrescar=seccion, seccion=seccion)


@login_required
@require_POST
def subir_fotos(request, pk):
    invitacion = _invitacion_de(request, pk)
    archivos = request.FILES.getlist('imagenes')
    disponibles = MAX_FOTOS - invitacion.fotos.count()
    if not archivos:
        return JsonResponse({'ok': False, 'message': 'Elige al menos una imagen.'}, status=400)
    if disponibles <= 0:
        return JsonResponse({'ok': False, 'message': f'La galería admite hasta {MAX_FOTOS} fotos.'}, status=400)
    campo = forms.ImageField()
    ultimo = invitacion.fotos.order_by('-orden').first()
    orden = (ultimo.orden + 1) if ultimo else 0
    guardadas, rechazadas = 0, []
    for archivo in archivos[:disponibles]:
        try:
            campo.clean(archivo)
            validar_peso(archivo, MAX_IMAGEN_MB)
        except forms.ValidationError:
            rechazadas.append(archivo.name)
            continue
        FotoInvitacion.objects.create(invitacion=invitacion, imagen=archivo, orden=orden)
        orden += 1
        guardadas += 1
    mensaje = f'{guardadas} foto{"s" if guardadas != 1 else ""} agregada{"s" if guardadas != 1 else ""}.'
    if rechazadas:
        mensaje += f' No se pudieron subir: {", ".join(rechazadas[:3])}.'
    return respuesta_ok(request, mensaje, recargar=False, refrescar='galeria', seccion='galeria')
