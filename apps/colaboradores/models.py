from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.utils import iniciales


class Colaborador(models.Model):
    """Sub-agencia o proveedor que opera eventos bajo la marca Grupo EM."""

    class Tipo(models.TextChoices):
        SONIDO = 'sonido', 'Sonido / DJ'
        AGENCIA = 'agencia', 'Agencia de eventos'
        SALON = 'salon', 'Salón / Jardín'
        FOTO = 'foto', 'Foto y video'
        BANQUETE = 'banquete', 'Banquetes'
        DECORACION = 'decoracion', 'Decoración'
        OTRO = 'otro', 'Otro'

    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.SONIDO)
    eslogan = models.TextField(blank=True, null=True)
    descripcion = models.TextField('descripción', blank=True)
    ciudad = models.CharField(max_length=120, blank=True)

    responsable = models.CharField('persona de contacto', max_length=120, blank=True)
    telefono = models.CharField('teléfono', max_length=30, blank=True)
    email = models.EmailField('correo', blank=True)
    whatsapp = models.CharField(max_length=50, blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    tiktok = models.URLField('TikTok', blank=True, null=True)
    sitio_web = models.URLField('sitio web', blank=True)

    logo_principal = models.ImageField(
        upload_to='sonidos/', blank=True, null=True,
        help_text='Se muestra en la pantalla del QR / proyector y en el panel.',
    )
    logo_secundario = models.ImageField(
        upload_to='sonidos/', blank=True, null=True,
        help_text='Versión para el pie de la pantalla de invitados (fondo oscuro).',
    )
    color_marca = models.CharField(
        'color de marca', max_length=7, default='#0098DA',
        help_text='Se usa como acento en las pantallas de invitados.',
    )
    estado = models.BooleanField('activo', default=True)
    fecha_registro = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = 'eventos_sonidodj'  # tabla heredada (antes "SonidoDJ")
        ordering = ['nombre']
        verbose_name = 'colaborador'
        verbose_name_plural = 'colaboradores'

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse('colaboradores:detalle', args=[self.pk])

    ICONOS = {
        'sonido': 'ph ph-headphones',
        'agencia': 'ph ph-briefcase',
        'salon': 'ph ph-buildings',
        'foto': 'ph ph-camera',
        'banquete': 'ph ph-fork-knife',
        'decoracion': 'ph ph-flower',
        'otro': 'ph ph-storefront',
    }

    @property
    def icono(self):
        return self.ICONOS.get(self.tipo, self.ICONOS['otro'])

    @property
    def iniciales(self):
        return iniciales(self.nombre)

    @property
    def logo(self):
        return self.logo_principal or self.logo_secundario

    @property
    def logo_pie(self):
        return self.logo_secundario or self.logo_principal

    @property
    def whatsapp_url(self):
        numero = ''.join(c for c in (self.whatsapp or '') if c.isdigit())
        if not numero:
            return ''
        if len(numero) == 10:  # número mexicano sin lada internacional
            numero = '52' + numero
        return f'https://wa.me/{numero}'
