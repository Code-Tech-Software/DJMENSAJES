from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone


class MensajeQuerySet(models.QuerySet):
    def fotos_album(self):
        """Fotos aprobadas por el DJ: salen en la pantalla y forman el álbum digital."""
        return self.filter(tipo=Mensaje.Tipo.FOTO, estatus=Mensaje.Estatus.ATENDIDO)

    def saludos_album(self):
        """Saludos que no fueron descartados."""
        return self.filter(tipo=Mensaje.Tipo.SALUDO).exclude(estatus=Mensaje.Estatus.DESCARTADO)

    def en_proyector(self):
        return self.filter(en_pantalla=True).exclude(estatus=Mensaje.Estatus.DESCARTADO)


class Mensaje(models.Model):
    """Saludo, petición de canción o foto enviada por un invitado durante el evento."""

    class Tipo(models.TextChoices):
        SALUDO = 'saludo', 'Saludo'
        CANCION = 'cancion', 'Canción'
        FOTO = 'foto', 'Foto'

    class Estatus(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        ATENDIDO = 'atendido', 'Atendido'
        DESCARTADO = 'descartado', 'Descartado'

    evento = models.ForeignKey('eventos.Evento', on_delete=models.CASCADE, related_name='mensajes')
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50, choices=Tipo.choices)
    mensaje = models.TextField(help_text='Texto del saludo, título de la canción o pie de la foto.')
    artista = models.CharField(max_length=120, blank=True)
    destinatario = models.CharField('para', max_length=120, blank=True)
    foto = models.ImageField(upload_to='envivo/fotos/%Y/%m/', blank=True)
    miniatura = models.ImageField(upload_to='envivo/fotos/mini/%Y/%m/', blank=True)
    foto_ancho = models.PositiveSmallIntegerField(default=0, editable=False)
    foto_alto = models.PositiveSmallIntegerField(default=0, editable=False)
    vip = models.BooleanField(default=False)
    estatus = models.CharField(max_length=20, choices=Estatus.choices, default=Estatus.PENDIENTE)
    en_pantalla = models.BooleanField('en proyector', default=False)
    sesion = models.CharField(max_length=40, blank=True, db_index=True, editable=False)
    ip = models.GenericIPAddressField(null=True, blank=True, editable=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    atendido_en = models.DateTimeField(null=True, blank=True)

    objects = MensajeQuerySet.as_manager()

    class Meta:
        db_table = 'eventos_mensaje'  # tabla heredada
        ordering = ['-fecha_creacion']
        verbose_name = 'mensaje'
        verbose_name_plural = 'mensajes'
        indexes = [models.Index(fields=['evento', '-fecha_creacion'])]

    def __str__(self):
        return f'{self.nombre} ({self.get_tipo_display()})'

    @property
    def es_foto(self):
        return self.tipo == self.Tipo.FOTO

    def marcar(self, estatus):
        self.estatus = estatus
        self.atendido_en = timezone.now() if estatus == self.Estatus.ATENDIDO else None

    def _datos_foto(self):
        if not (self.es_foto and self.foto):
            return {}
        return {
            'foto': self.foto.url,
            'miniatura': self.miniatura.url if self.miniatura else self.foto.url,
            'ancho': self.foto_ancho,
            'alto': self.foto_alto,
        }

    def a_dict(self):
        local = timezone.localtime(self.fecha_creacion)
        return {
            'id': self.pk,
            'nombre': self.nombre,
            'tipo': self.tipo,
            'mensaje': self.mensaje,
            'artista': self.artista,
            'destinatario': self.destinatario,
            'vip': self.vip,
            'estatus': self.estatus,
            'en_pantalla': self.en_pantalla,
            'hora': local.strftime('%H:%M'),
            'fecha': local.isoformat(),
            'atendido_hora': timezone.localtime(self.atendido_en).strftime('%H:%M') if self.atendido_en else '',
            **self._datos_foto(),
        }

    def a_dict_pantalla(self):
        return {
            'id': self.pk,
            'tipo': self.tipo,
            'nombre': self.nombre,
            'mensaje': self.mensaje,
            'destinatario': self.destinatario,
            'vip': self.vip,
            **self._datos_foto(),
        }


@receiver(post_delete, sender=Mensaje)
def borrar_archivos_foto(sender, instance, **kwargs):
    """Al borrar un mensaje (o su evento) también se borran la foto y su miniatura."""
    for archivo in (instance.foto, instance.miniatura):
        if archivo:
            try:
                archivo.delete(save=False)
            except Exception:  # el almacenamiento no debe impedir borrar el registro
                pass
