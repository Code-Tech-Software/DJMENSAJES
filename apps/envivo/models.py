from django.db import models
from django.utils import timezone


class Mensaje(models.Model):
    """Saludo o petición de canción enviada por un invitado durante el evento."""

    class Tipo(models.TextChoices):
        SALUDO = 'saludo', 'Saludo'
        CANCION = 'cancion', 'Canción'

    class Estatus(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        ATENDIDO = 'atendido', 'Atendido'
        DESCARTADO = 'descartado', 'Descartado'

    evento = models.ForeignKey('eventos.Evento', on_delete=models.CASCADE, related_name='mensajes')
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50, choices=Tipo.choices)
    mensaje = models.TextField()
    artista = models.CharField(max_length=120, blank=True)
    destinatario = models.CharField('para', max_length=120, blank=True)
    vip = models.BooleanField(default=False)
    estatus = models.CharField(max_length=20, choices=Estatus.choices, default=Estatus.PENDIENTE)
    en_pantalla = models.BooleanField('en proyector', default=False)
    sesion = models.CharField(max_length=40, blank=True, db_index=True, editable=False)
    ip = models.GenericIPAddressField(null=True, blank=True, editable=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    atendido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'eventos_mensaje'  # tabla heredada
        ordering = ['-fecha_creacion']
        verbose_name = 'mensaje'
        verbose_name_plural = 'mensajes'
        indexes = [models.Index(fields=['evento', '-fecha_creacion'])]

    def __str__(self):
        return f'{self.nombre} ({self.get_tipo_display()})'

    def marcar(self, estatus):
        self.estatus = estatus
        self.atendido_en = timezone.now() if estatus == self.Estatus.ATENDIDO else None

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
        }

    def a_dict_pantalla(self):
        return {
            'id': self.pk,
            'nombre': self.nombre,
            'mensaje': self.mensaje,
            'destinatario': self.destinatario,
            'vip': self.vip,
        }
