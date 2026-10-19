"""Piezas reutilizables para vistas con formularios en modal (AJAX) y respuestas JSON."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect, JsonResponse


def es_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def respuesta_ok(request, mensaje='', *, redirect=None, recargar=True, respaldo='/', **extra):
    """
    Respuesta de éxito uniforme.
    - AJAX: JSON que el front interpreta (toast + recarga/redirección).
    - Normal: mensaje flash y redirección.
    """
    if es_ajax(request):
        datos = {'ok': True, 'message': mensaje, **extra}
        if redirect:
            datos['redirect'] = str(redirect)
        elif recargar:
            datos['reload'] = True
        return JsonResponse(datos)
    if mensaje:
        messages.success(request, mensaje)
    return HttpResponseRedirect(redirect or request.META.get('HTTP_REFERER') or respaldo)


def respuesta_error(request, mensaje, status=400):
    if es_ajax(request):
        return JsonResponse({'ok': False, 'message': mensaje}, status=status)
    messages.error(request, mensaje)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER') or '/')


class FormularioModalMixin:
    """
    Para CreateView / UpdateView / FormView:
    - GET por AJAX devuelve solo el contenido del modal.
    - GET normal muestra el mismo formulario en una página completa (respaldo).
    - POST inválido por AJAX responde 422 con el modal re-renderizado con errores.
    - POST válido responde JSON (AJAX) o redirige con mensaje.
    """
    template_modal = None
    titulo = ''
    subtitulo = ''
    icono = 'ph ph-pencil-simple'
    tamano = ''
    texto_boton = 'Guardar'
    mensaje_exito = 'Cambios guardados.'
    recargar = True

    def get_template_names(self):
        if es_ajax(self.request):
            return [self.template_modal]
        return ['components/pagina_modal.html']

    def get_titulo(self):
        return self.titulo

    def get_subtitulo(self):
        return self.subtitulo

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update({
            'template_modal': self.template_modal,
            'titulo': self.get_titulo(),
            'subtitulo': self.get_subtitulo(),
            'icono': self.icono,
            'tamano': self.tamano,
            'texto_boton': self.texto_boton,
            'accion': self.request.get_full_path(),
            'es_modal': es_ajax(self.request),
        })
        return contexto

    def form_invalid(self, form):
        respuesta = super().form_invalid(form)
        if es_ajax(self.request):
            respuesta.status_code = 422
        return respuesta

    def form_valid(self, form):
        self.object = form.save()
        return self.respuesta_exito()

    def get_mensaje_exito(self):
        return self.mensaje_exito

    def get_url_exito(self):
        """URL a la que se navega tras guardar. None = recargar la página actual."""
        siguiente = self.request.GET.get('next')
        if siguiente and siguiente.startswith('/'):
            return siguiente
        return None

    def respuesta_exito(self):
        respaldo = '/'
        objeto = getattr(self, 'object', None)
        if objeto is not None and hasattr(objeto, 'get_absolute_url'):
            respaldo = objeto.get_absolute_url()
        return respuesta_ok(
            self.request, self.get_mensaje_exito(),
            redirect=self.get_url_exito(), recargar=self.recargar, respaldo=respaldo,
        )


class FormularioConAgenciaMixin:
    """Los formularios con listas de sub-agencias o banners (usa_agencia = True) reciben la agencia."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if getattr(self.get_form_class(), 'usa_agencia', False):
            kwargs['agencia_id'] = self.request.user.agencia_id
        return kwargs


class AsignarAgenciaMixin(FormularioConAgenciaMixin):
    """
    Para las vistas que crean algo de una agencia (evento, sub-agencia, banner, integrante):
    queda en la agencia de quien lo crea. Una cuenta sin agencia (de EventPro) no puede crear.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.agencia_id:
            raise PermissionDenied('Tu cuenta no pertenece a ninguna agencia.')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.agencia_id = self.request.user.agencia_id
        return super().form_valid(form)


class DeLaAgenciaMixin(FormularioConAgenciaMixin):
    """Para editar o ver registros de una agencia: los de otra agencia dan 404 aunque se cambie el número."""

    def get_queryset(self):
        return super().get_queryset().filter(agencia_id=self.request.user.agencia_id)
