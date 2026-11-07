"""El portal del cliente desde el panel de la agencia: enviarlo por WhatsApp y sus opciones."""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import UpdateView

from apps.core.marca import Marca
from apps.core.mixins import FormularioModalMixin

from ..views import obtener_evento
from .forms import PortalOpcionesForm
from .servicios import obtener_portal, url_whatsapp


@login_required
def enviar(request, pk):
    """Abre WhatsApp con el mensaje y el enlace del portal; queda marcado como enviado."""
    evento = obtener_evento(request, pk)
    portal = obtener_portal(evento)
    if not portal.enviado_el:
        portal.enviado_el = timezone.now()
        portal.save(update_fields=['enviado_el'])
    return redirect(url_whatsapp(portal, request.build_absolute_uri(portal.get_absolute_url()), Marca(evento).nombre))


class PortalOpciones(LoginRequiredMixin, FormularioModalMixin, UpdateView):
    form_class = PortalOpcionesForm
    template_modal = 'eventos/portal/form_opciones.html'
    icono = 'ph ph-user-circle-gear'
    titulo = 'Portal del cliente'
    texto_boton = 'Guardar'
    mensaje_exito = 'Portal actualizado.'

    def get_object(self, queryset=None):
        return obtener_portal(obtener_evento(self.request, self.kwargs['pk']))

    def get_subtitulo(self):
        return self.object.evento.nombre_evento
