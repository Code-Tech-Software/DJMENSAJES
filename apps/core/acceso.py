"""
Acceso al panel según la vigencia de la agencia.

Una agencia suspendida o vencida no puede usar el panel (ve una página con cómo renovar). Las páginas
públicas —invitación, pantallas, panel del DJ, álbum, anfitriones— siguen funcionando: los invitados de un
evento ya contratado no deben pagar las consecuencias.

Se aplica a las rutas del panel desde DJMENSAJES/urls.py con decorar_urls() en lugar de un middleware,
para no tocar settings.py.
"""
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import render
from django.urls import URLResolver

from .mixins import es_ajax
from .models import Ajustes

# Sesión de soporte: el superusuario que "entró como" alguien (consola → Entrar como)
IMPERSONADOR = 'eventpro_impersonador'


def acceso_bloqueado(request):
    agencia = request.user.agencia
    if es_ajax(request):
        return JsonResponse({'ok': False, 'message': 'El acceso de tu agencia está suspendido.'}, status=403)
    return render(request, 'core/acceso_bloqueado.html', {
        'agencia': agencia,
        'contacto': Ajustes.plataforma(),
    }, status=403)


def agencia_vigente(vista):
    """Bloquea la vista a quien pertenece a una agencia suspendida o vencida (o a ninguna).
    Las cuentas de EventPro (superusuarios) siempre pasan, también cuando entran como alguien para dar soporte."""
    if getattr(vista, 'requiere_agencia_vigente', False):
        return vista  # ya protegida (p. ej. si las rutas se cargan dos veces)

    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        usuario = getattr(request, 'user', None)
        if usuario is not None and usuario.is_authenticated and not usuario.is_superuser and not request.session.get(IMPERSONADOR):
            if usuario.agencia is None or not usuario.agencia.vigente:
                return acceso_bloqueado(request)
        return vista(request, *args, **kwargs)

    envoltura.requiere_agencia_vigente = True
    return envoltura


def decorar_urls(patrones, decorador, excepto=()):
    """Aplica el decorador a todas las rutas (y sub-rutas) salvo las nombradas en `excepto`."""
    for patron in patrones:
        if isinstance(patron, URLResolver):
            decorar_urls(patron.url_patterns, decorador, excepto)
        elif patron.name not in excepto:
            patron.callback = decorador(patron.callback)
    return patrones
