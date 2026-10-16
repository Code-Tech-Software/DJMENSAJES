from django.urls import reverse

from apps.eventos.models import Evento


def interfaz(request):
    """Datos globales del panel: permisos, contadores y acciones de la paleta (Ctrl+K)."""
    usuario = getattr(request, 'user', None)
    if not usuario or not usuario.is_authenticated:
        return {}
    match = getattr(request, 'resolver_match', None)
    if match and match.namespace in ('envivo', 'invitacion_publica'):
        return {}

    from apps.core.actividad import contar_no_vistas

    acciones = [
        {'titulo': 'Nuevo evento', 'sub': 'Registrar un evento', 'url': reverse('eventos:crear'), 'icono': 'ri-add-circle-line', 'modal': True},
        {'titulo': 'Dashboard', 'sub': 'Resumen general', 'url': reverse('core:dashboard'), 'icono': 'ri-dashboard-3-line'},
        {'titulo': 'Calendario', 'sub': 'Agenda de eventos', 'url': reverse('eventos:calendario'), 'icono': 'ri-calendar-2-line'},
        {'titulo': 'Eventos', 'sub': 'Lista completa', 'url': reverse('eventos:lista'), 'icono': 'ri-sparkling-2-line'},
        {'titulo': 'Mi perfil', 'sub': 'Datos y contraseña', 'url': reverse('cuentas:perfil'), 'icono': 'ri-user-smile-line'},
    ]
    if usuario.ve_todo:
        acciones += [
            {'titulo': 'Colaboradores', 'sub': 'Sub-agencias', 'url': reverse('colaboradores:lista'), 'icono': 'ri-team-line'},
            {'titulo': 'Nuevo colaborador', 'sub': 'Registrar sub-agencia', 'url': reverse('colaboradores:crear'), 'icono': 'ri-user-add-line', 'modal': True},
            {'titulo': 'Banners', 'sub': 'Fondos visuales', 'url': reverse('banners:lista'), 'icono': 'ri-image-2-line'},
        ]
    if usuario.es_admin:
        acciones.append({'titulo': 'Equipo', 'sub': 'Usuarios y roles', 'url': reverse('cuentas:usuarios'), 'icono': 'ri-shield-user-line'})

    return {
        'es_admin': usuario.es_admin,
        've_todo': usuario.ve_todo,
        'acciones_paleta': acciones,
        'notificaciones_nuevas': contar_no_vistas(usuario),
        'total_proximos': Evento.objects.visibles_para(usuario).vigentes().proximos().count(),
    }
