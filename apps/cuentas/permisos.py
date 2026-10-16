"""Reglas de acceso por rol."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


def es_admin(usuario):
    return usuario.is_authenticated and usuario.es_admin


def gestiona_catalogos(usuario):
    """Administradores y coordinadores gestionan colaboradores y banners."""
    return usuario.is_authenticated and usuario.ve_todo


def admin_requerido(vista):
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not es_admin(request.user):
            raise PermissionDenied
        return vista(request, *args, **kwargs)
    return envoltura


def catalogos_requerido(vista):
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not gestiona_catalogos(request.user):
            raise PermissionDenied
        return vista(request, *args, **kwargs)
    return envoltura


class AdminRequeridoMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return es_admin(self.request.user)


class CatalogosRequeridoMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return gestiona_catalogos(self.request.user)
