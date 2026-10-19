"""
"Entrar como": el superusuario entra al panel de una agencia como uno de sus usuarios para darle soporte.
Queda en la bitácora y una barra en cada página recuerda que se está viendo como otra persona.
"""
from django.contrib.auth import login
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.cuentas.models import Usuario

from ..acceso import IMPERSONADOR
from ..bitacora import Accion, registrar
from ..mixins import respuesta_ok
from . import solo_plataforma

BACKEND = 'django.contrib.auth.backends.ModelBackend'


@solo_plataforma
@require_POST
def entrar_como(request, pk):
    destino = get_object_or_404(Usuario, pk=pk, is_superuser=False, is_active=True, agencia__isnull=False)
    original = request.user
    ultimo_acceso = destino.last_login
    request.cambio_de_cuenta = True  # no se anota como inicio de sesión normal
    login(request, destino, backend=BACKEND)
    Usuario.objects.filter(pk=destino.pk).update(last_login=ultimo_acceso)  # su "último acceso" real no cambia
    request.session[IMPERSONADOR] = original.pk
    registrar(Accion.ENTRAR_COMO, actor=original, usuario=destino, detalle=f'Soporte como @{destino.username}', request=request)
    return respuesta_ok(request, f'Ahora ves EventPro como {destino}.', redirect=reverse('core:dashboard'))


@require_POST
def salir_de(request):
    """Regresa a la cuenta de EventPro. Solo existe durante una sesión de soporte."""
    original = Usuario.objects.filter(pk=request.session.get(IMPERSONADOR) or 0, is_superuser=True, is_active=True).first()
    if original is None or not request.user.is_authenticated:
        raise Http404
    destino = request.user
    request.cambio_de_cuenta = True
    login(request, original, backend=BACKEND)
    registrar(Accion.SALIR_DE, actor=original, usuario=destino, detalle=f'Terminó el soporte como @{destino.username}', request=request)
    return redirect('plataforma:agencia', destino.agencia_id) if destino.agencia_id else redirect('plataforma:dashboard')
