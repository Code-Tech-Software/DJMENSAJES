"""Contacto de EventPro para que las agencias por vencer o suspendidas pidan su renovación."""
from django.views.generic import UpdateView

from ..mixins import FormularioModalMixin
from ..models import Ajustes
from . import PlataformaMixin
from .forms import ContactoPlataformaForm


class ContactoEditar(PlataformaMixin, FormularioModalMixin, UpdateView):
    form_class = ContactoPlataformaForm
    template_modal = 'core/consola/form_contacto.html'
    titulo = 'Contacto para renovar'
    subtitulo = 'Lo ven las agencias por vencer o suspendidas.'
    icono = 'ph ph-whatsapp-logo'
    tamano = 'sm'
    mensaje_exito = 'Contacto guardado.'

    def get_object(self, queryset=None):
        return Ajustes.plataforma()
