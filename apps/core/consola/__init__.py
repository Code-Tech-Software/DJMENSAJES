"""
Consola de EventPro: la administración de la plataforma (solo superusuarios).

Dashboard, agencias, usuarios de todas las agencias, pagos, planes con límites, bitácora y
"entrar como" para dar soporte. Las vistas viven en los módulos de este paquete.
"""
import calendar
import secrets
from datetime import date
from functools import wraps
from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.urls import reverse
from django.utils.text import slugify

from ..models import Agencia
from ..utils import generar_codigo

CLAVE_ACCESO = 'plataforma_acceso'


def solo_plataforma(vista):
    """Solo las cuentas de EventPro (superusuarios); para cualquier otro la página no existe."""
    @login_required
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise Http404
        return vista(request, *args, **kwargs)
    return envoltura


class PlataformaMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            raise Http404
        return super().dispatch(request, *args, **kwargs)


def sumar_meses(fecha, meses):
    mes = fecha.month - 1 + meses
    anio, mes = fecha.year + mes // 12, mes % 12 + 1
    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))


def clave_temporal():
    """Fácil de dictar o copiar: 5 letras y 4 números, sin caracteres que se confundan."""
    return (''.join(secrets.choice('abcdefghjkmnpqrstuvwxyz') for _ in range(5))
            + ''.join(secrets.choice('23456789') for _ in range(4)))


def slug_para(nombre):
    base = slugify(nombre)[:50].strip('-') or 'agencia'
    slug = base
    while Agencia.objects.filter(slug=slug).exists():
        slug = f'{base}-{generar_codigo(4)}'
    return slug


def recordar_acceso(request, usuario, clave, pagina):
    """El acceso nuevo se muestra una sola vez (en `pagina`); la contraseña no se guarda en claro."""
    request.session[CLAVE_ACCESO] = {
        'pagina': pagina, 'usuario': usuario.username, 'nombre': usuario.get_full_name() or usuario.username,
        'agencia': usuario.agencia.nombre if usuario.agencia_id else '', 'clave': clave,
    }


def tomar_acceso(request, pagina):
    """El acceso pendiente de mostrar en esta página (y se olvida)."""
    acceso = request.session.get(CLAVE_ACCESO)
    if not acceso or acceso.get('pagina') != pagina:
        return None
    del request.session[CLAVE_ACCESO]
    url = request.build_absolute_uri(reverse('cuentas:login'))
    acceso['url'] = url
    donde = f' para {acceso["agencia"]}' if acceso['agencia'] else ''
    acceso['whatsapp'] = 'https://wa.me/?text=' + quote(
        f"¡Hola {acceso['nombre']}! Ya tienes acceso a EventPro{donde}.\n"
        f"Entra en: {url}\nUsuario: {acceso['usuario']}\nContraseña temporal: {acceso['clave']}\n"
        'Al entrar, cámbiala desde tu perfil.')
    return acceso
