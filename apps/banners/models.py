from django.db import models
from django.db.models import Q
from django.utils import timezone


class BannerQuerySet(models.QuerySet):
    def disponibles_para(self, agencia_id):
        """Los de la agencia y los de la biblioteca de EventPro (sin agencia)."""
        return self.filter(Q(agencia_id=agencia_id) | Q(agencia__isnull=True))


class Banner(models.Model):
    """Paquete de fondos visuales que se aplica a las pantallas y a la invitación de un evento."""

    class Categoria(models.TextChoices):
        GENERAL = 'general', 'General'
        BODA = 'boda', 'Boda'
        XV = 'xv', 'XV Años'
        INFANTIL = 'infantil', 'Infantil'
        FIESTA = 'fiesta', 'Fiesta / Antro'
        CORPORATIVO = 'corporativo', 'Corporativo'

    nombre = models.CharField(max_length=200)
    descripcion = models.TextField('descripción', blank=True, null=True)
    categoria = models.CharField('categoría', max_length=20, choices=Categoria.choices, default=Categoria.GENERAL)
    fondo_movil = models.ImageField(
        'fondo vertical', upload_to='banners/', blank=True, null=True,
        help_text='Pantalla de invitados en el celular (vertical, 1080×1920 ideal).',
    )
    fondo_pantalla = models.ImageField(
        'fondo horizontal', upload_to='banners/', blank=True, null=True,
        help_text='Pantalla del QR / proyector (horizontal, 1920×1080 ideal).',
    )
    portada = models.ImageField(
        upload_to='banners/', blank=True, null=True,
        help_text='Portada sugerida para la invitación digital.',
    )
    # Sin agencia = biblioteca de EventPro, disponible para todas las agencias
    agencia = models.ForeignKey(
        'core.Agencia', on_delete=models.PROTECT, null=True, blank=True, related_name='banners', editable=False,
    )
    colaborador = models.ForeignKey(
        'colaboradores.Colaborador', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='banners', help_text='Déjalo vacío para que todos puedan usarlo.',
    )
    estado = models.BooleanField('activo', default=True)
    creado = models.DateTimeField(default=timezone.now, editable=False)

    objects = BannerQuerySet.as_manager()

    class Meta:
        db_table = 'eventos_banner'  # tabla heredada
        ordering = ['-creado', '-id']
        verbose_name = 'banner'
        verbose_name_plural = 'banners'

    def __str__(self):
        return self.nombre

    @property
    def imagen_movil(self):
        return self.fondo_movil or self.fondo_pantalla or self.portada

    @property
    def imagen_pantalla(self):
        return self.fondo_pantalla or self.fondo_movil or self.portada

    @property
    def imagen_portada(self):
        return self.portada or self.fondo_pantalla or self.fondo_movil

    @property
    def miniatura(self):
        return self.portada or self.fondo_pantalla or self.fondo_movil
