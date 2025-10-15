from django.db import models
from django.contrib.auth.models import User

class Evento(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='eventos')
    nombre_evento = models.CharField(max_length=200)
    tipo_evento = models.CharField(
        max_length=50,
        choices=[
            ('boda', 'Boda'),
            ('quinse', 'Quince Años'),
            ('cumple', 'Cumpleaños'),
            ('otro', 'Otro'),
        ]
    )
    password_vip = models.CharField(max_length=100)
    banner = models.CharField(
        max_length=100,
        choices=[
            ('banner1', 'Banner 1'),
            ('banner2', 'Banner 2'),
            ('banner3', 'Banner 3'),
        ]
    )
    sonido_dj = models.CharField(
        max_length=100,
        choices=[
            ('dj1', 'Sonido DJ 1'),
            ('dj2', 'Sonido DJ 2'),
            ('dj3', 'Sonido DJ 3'),
        ]
    )
    fecha_inicio_evento = models.DateTimeField()
    fecha_fin_evento = models.DateTimeField()
    cooldown = models.FloatField(help_text="Tiempo en minutos para enviar nuevo mensaje")
    estado = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre_evento} ({self.usuario.username})"


class Mensaje(models.Model):
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(
        max_length=50,
        choices=[
            ('saludo', 'Saludo'),
            ('cancion', 'Canción'),
        ]
    )
    mensaje = models.TextField()
    vip = models.BooleanField(default=False)
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='mensajes')
    estado = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} ({self.tipo})"
