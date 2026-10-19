"""Anotaciones automáticas en la bitácora (inicios de sesión y eventos nuevos)."""
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver

from .bitacora import Accion, registrar


@receiver(user_logged_in, dispatch_uid='bitacora_inicio_sesion')
def inicio_de_sesion(sender, request, user, **kwargs):
    if getattr(request, 'cambio_de_cuenta', False):  # "entrar como" se anota aparte
        return
    registrar(Accion.INICIO_SESION, actor=user, agencia=user.agencia if user.agencia_id else None, request=request)


@receiver(post_save, sender='eventos.Evento', dispatch_uid='bitacora_evento_creado')
def evento_creado(sender, instance, created, **kwargs):
    if created and not kwargs.get('raw'):
        registrar(Accion.EVENTO_CREADO, actor=instance.creado_por, agencia=instance.agencia, detalle=instance.nombre_evento)
