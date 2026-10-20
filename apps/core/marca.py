"""
La marca que ven los invitados de un evento (pantallas, invitación, álbum y panel de anfitriones):
la de su sub-agencia si tiene una; si no, la de su agencia (sus Ajustes). EventPro solo aparece
como crédito discreto ("Con tecnología de EventPro").
"""
from apps.core.models import Ajustes

COLOR_POR_DEFECTO = '#0098DA'


class Marca:
    def __init__(self, evento):  # también sirve con una cotización (tiene agencia y sub-agencia)
        self.colaborador = evento.colaborador
        self.ajustes = Ajustes.de(evento.agencia_id)
        origen = self.colaborador or self.ajustes
        self.de_subagencia = self.colaborador is not None
        self.nombre = origen.nombre
        self.eslogan = origen.eslogan or ''
        self.color = origen.color_marca or COLOR_POR_DEFECTO
        self.logo = origen.logo  # para fondo oscuro: proyector, chip del pie de la invitación
        self.logo_pie = origen.logo_pie
        self.whatsapp_url = origen.whatsapp_url
        self.telefono = origen.telefono or ''
        self.email = origen.email or ''
        self.instagram = origen.instagram or ''
        self.facebook = origen.facebook or ''
        self.tiktok = origen.tiktok or ''
        self.sitio_web = origen.sitio_web or ''
        self.icono = self.colaborador.icono if self.colaborador else 'ph ph-storefront'

    @property
    def tiene_redes(self):
        return bool(self.instagram or self.facebook or self.tiktok or self.sitio_web)
