from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.utils import iniciales


class Usuario(AbstractUser):
    """Miembro del equipo. Puede pertenecer a un colaborador (sub-agencia)."""

    class Rol(models.TextChoices):
        ADMIN = 'admin', 'Administrador'
        COORDINADOR = 'coordinador', 'Coordinador'
        COLABORADOR = 'colaborador', 'Colaborador'

    telefono = models.CharField('teléfono', max_length=15, blank=True, null=True)
    direccion = models.TextField('dirección', blank=True, null=True)
    foto = models.ImageField(upload_to='fotos_perfil/', blank=True, null=True)
    rol = models.CharField(
        max_length=20, choices=Rol.choices, default=Rol.COORDINADOR,
        help_text='Define qué secciones y eventos puede ver.',
    )
    agencia = models.ForeignKey(
        'core.Agencia', on_delete=models.PROTECT, null=True, blank=True, related_name='usuarios',
        help_text='Agencia cliente de EventPro. Vacío = cuenta de EventPro (sin agencia).',
    )
    colaborador = models.ForeignKey(
        'colaboradores.Colaborador', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='usuarios', help_text='Sub-agencia a la que pertenece.',
    )
    cargo = models.CharField(max_length=80, blank=True)
    notificaciones_vistas_en = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        # La tabla se creó cuando el modelo vivía en la app "eventos"; se conserva el nombre
        db_table = 'eventos_usuario'
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def es_admin(self):
        return self.is_superuser or self.rol == self.Rol.ADMIN

    @property
    def ve_todo(self):
        """Administradores y coordinadores ven los eventos de todas las sub-agencias."""
        return self.es_admin or self.rol == self.Rol.COORDINADOR

    @property
    def nombre_corto(self):
        return self.first_name or self.username

    @property
    def iniciales(self):
        return iniciales(self.get_full_name() or self.username)

    @property
    def rol_visible(self):
        return 'Superusuario' if self.is_superuser and self.rol != self.Rol.ADMIN else self.get_rol_display()
