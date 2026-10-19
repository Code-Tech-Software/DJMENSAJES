from django.urls import reverse
from django.utils.functional import SimpleLazyObject

from apps.core.acceso import IMPERSONADOR
from apps.core.models import Agencia, Ajustes
from apps.eventos.models import Evento


def interfaz(request):
    """Datos globales: ajustes del negocio (en todas las páginas) y, en el panel,
    permisos, contadores y acciones de la paleta (Ctrl+K)."""
    usuario = getattr(request, 'user', None)
    # Ajustes de la agencia de quien usa el panel. Las páginas públicas (invitación, pantallas, álbum)
    # pasan en su contexto los de la agencia del evento, que tienen prioridad sobre estos.
    agencia_id = usuario.agencia_id if usuario is not None and usuario.is_authenticated else None
    base = {'ajustes': SimpleLazyObject(lambda: Ajustes.de(agencia_id))}
    if not usuario or not usuario.is_authenticated:
        return base
    match = getattr(request, 'resolver_match', None)
    if match and match.namespace in ('envivo', 'invitacion_publica'):
        return base

    from apps.core.actividad import contar_no_vistas

    acciones = [
        {'titulo': 'Nuevo evento', 'sub': 'Registrar un evento', 'url': reverse('eventos:crear'), 'icono': 'ph ph-plus-circle', 'modal': True},
        {'titulo': 'Dashboard', 'sub': 'Resumen general', 'url': reverse('core:dashboard'), 'icono': 'ph ph-gauge'},
        {'titulo': 'Calendario', 'sub': 'Agenda de eventos', 'url': reverse('eventos:calendario'), 'icono': 'ph ph-calendar'},
        {'titulo': 'Eventos', 'sub': 'Lista completa', 'url': reverse('eventos:lista'), 'icono': 'ph ph-sparkle'},
        {'titulo': 'Mi perfil', 'sub': 'Datos y contraseña', 'url': reverse('cuentas:perfil'), 'icono': 'ph ph-user-circle'},
        {'titulo': 'Ajustes', 'sub': 'Apariencia, negocio y eventos nuevos', 'url': reverse('core:ajustes'), 'icono': 'ph ph-gear-six'},
    ]
    if usuario.ve_todo:
        acciones += [
            {'titulo': 'Colaboradores', 'sub': 'Sub-agencias', 'url': reverse('colaboradores:lista'), 'icono': 'ph ph-users-three'},
            {'titulo': 'Nuevo colaborador', 'sub': 'Registrar sub-agencia', 'url': reverse('colaboradores:crear'), 'icono': 'ph ph-user-plus', 'modal': True},
            {'titulo': 'Banners', 'sub': 'Fondos visuales', 'url': reverse('banners:lista'), 'icono': 'ph ph-image'},
        ]
    if usuario.es_admin:
        acciones.append({'titulo': 'Equipo', 'sub': 'Usuarios y roles', 'url': reverse('cuentas:usuarios'), 'icono': 'ph ph-shield-check'})
    if usuario.is_superuser:
        acciones.append({'titulo': 'Agencias', 'sub': 'Panel de EventPro', 'url': reverse('plataforma:agencias'), 'icono': 'ph ph-buildings'})

    # Al administrador de una agencia por vencer se le avisa en todo el panel
    aviso_vigencia = None
    agencia = usuario.agencia if usuario.agencia_id else None
    if agencia and usuario.es_admin and agencia.estado == 'por_vencer':
        aviso_vigencia = {'dias': agencia.dias_restantes, 'fecha': agencia.vence_el, 'contacto': Ajustes.plataforma()}

    soporte = None
    if request.session.get(IMPERSONADOR):
        soporte = {'original': request.session.get(IMPERSONADOR)}
    consola_atencion = 0
    if usuario.is_superuser and match and match.namespace == 'plataforma':
        consola_atencion = sum(1 for a in Agencia.objects.only('activa', 'vence_el') if a.estado in ('por_vencer', 'vencida'))

    return {
        **base,
        'soporte': soporte,
        'consola_atencion': consola_atencion,
        'es_admin': usuario.es_admin,
        've_todo': usuario.ve_todo,
        'acciones_paleta': acciones,
        'aviso_vigencia': aviso_vigencia,
        'notificaciones_nuevas': contar_no_vistas(usuario),
        'total_proximos': Evento.objects.visibles_para(usuario).vigentes().proximos().count(),
    }
