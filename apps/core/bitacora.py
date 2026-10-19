"""Registro de lo que pasa en la plataforma (consola de EventPro → Bitácora)."""
import logging

from .models import Bitacora
from .utils import ip_cliente

Accion = Bitacora.Accion
log = logging.getLogger(__name__)


def registrar(accion, *, actor=None, agencia=None, usuario=None, detalle='', request=None):
    """Anota una acción. Nunca debe romper la operación que la provoca."""
    try:
        if actor is None and request is not None and request.user.is_authenticated:
            actor = request.user
        if agencia is None and usuario is not None:
            agencia = usuario.agencia if usuario.agencia_id else None
        Bitacora.objects.create(
            accion=accion,
            actor=actor if actor is not None and actor.pk else None,
            agencia=agencia,
            usuario=usuario,
            detalle=(detalle or '')[:255],
            ip=ip_cliente(request) if request is not None else None,
        )
    except Exception:  # la bitácora es informativa
        log.exception('No se pudo registrar en la bitácora: %s', accion)
