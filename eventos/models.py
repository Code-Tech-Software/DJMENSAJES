from django.db import models
from django.contrib.auth.models import User


class SonidoDJ(models.Model):
    nombre = models.CharField(max_length=200)
    eslogan = models.TextField(blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    whatsapp = models.CharField(max_length=50, blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    tiktok = models.URLField(blank=True, null=True)
    imagen1 = models.ImageField(upload_to='sonidos/', blank=True, null=True)
    imagen2 = models.ImageField(upload_to='sonidos/', blank=True, null=True)
    estado = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Banner(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    imagen1 = models.ImageField(upload_to='banners/', blank=True, null=True)
    imagen2 = models.ImageField(upload_to='banners/', blank=True, null=True)
    imagen3 = models.ImageField(upload_to='banners/', blank=True, null=True)
    estado = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


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
    banner = models.ForeignKey(Banner, on_delete=models.SET_NULL, null=True, blank=True, related_name='eventos')
    sonido_dj = models.ForeignKey(SonidoDJ, on_delete=models.SET_NULL, null=True, blank=True, related_name='eventos')

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
