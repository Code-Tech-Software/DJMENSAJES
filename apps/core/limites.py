"""
Límites del plan de cada agencia: eventos al mes, usuarios activos y sub-agencias (la bolsa de fotos al mes
vive en modulos.py y aquí solo se muestra su uso).
Sin plan, o con el límite vacío, no hay límite. Al llegar al tope ya no se puede crear más de eso.
"""
from django.utils import timezone

from .bitacora import Accion, registrar
from .mixins import respuesta_error
from .modulos import bolsa_del_mes, tiene

PORCENTAJE_AVISO = 80


def _inicio_de_mes():
    ahora = timezone.localtime()
    return ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _contar(agencia, recurso):
    if recurso == 'eventos':
        return agencia.eventos.filter(creado__gte=_inicio_de_mes()).count()
    if recurso == 'usuarios':
        return agencia.usuarios.filter(is_active=True).count()
    return agencia.colaboradores.count()


RECURSOS = {
    # recurso: (campo del plan, etiqueta, icono)
    'eventos': ('max_eventos_mes', 'Eventos este mes', 'ph ph-sparkle'),
    'usuarios': ('max_usuarios', 'Usuarios activos', 'ph ph-users'),
    'colaboradores': ('max_colaboradores', 'Sub-agencias', 'ph ph-users-three'),
}


def _fila(recurso, etiqueta, icono, usado, limite):
    porcentaje = min(100, round(usado * 100 / limite)) if limite else 0
    return {
        'recurso': recurso, 'etiqueta': etiqueta, 'icono': icono, 'usado': usado, 'limite': limite,
        'porcentaje': porcentaje, 'lleno': bool(limite is not None and usado >= limite),
        'cerca': bool(limite and porcentaje >= PORCENTAJE_AVISO),
    }


def uso(agencia):
    """Cuánto usa la agencia de cada límite de su plan (para barras de uso)."""
    plan = agencia.plan if agencia and agencia.plan_id else None
    filas = [_fila(recurso, etiqueta, icono, _contar(agencia, recurso), getattr(plan, campo) if plan else None)
             for recurso, (campo, etiqueta, icono) in RECURSOS.items()]
    if plan is not None and plan.max_fotos_mes is not None and tiene(agencia, 'fotos'):
        hoy = timezone.localdate()
        bolsa = bolsa_del_mes(agencia, hoy.year, hoy.month)
        filas.append(_fila('fotos', 'Fotos apartadas este mes', 'ph ph-images', bolsa['ocupadas'], bolsa['total']))
    return filas


def puede_crear(agencia, recurso):
    """(True, '') o (False, motivo) según el plan de la agencia."""
    if agencia is None or not agencia.plan_id:
        return True, ''
    campo, etiqueta, _ = RECURSOS[recurso]
    limite = getattr(agencia.plan, campo)
    if limite is None or _contar(agencia, recurso) < limite:
        return True, ''
    textos = {
        'eventos': f'Tu plan {agencia.plan} permite {limite} evento{"s" if limite != 1 else ""} al mes y ya llegaste al límite.',
        'usuarios': f'Tu plan {agencia.plan} permite {limite} usuario{"s" if limite != 1 else ""} activo{"s" if limite != 1 else ""} y ya llegaste al límite.',
        'colaboradores': f'Tu plan {agencia.plan} permite {limite} sub-agencia{"s" if limite != 1 else ""} y ya llegaste al límite.',
    }
    return False, textos[recurso] + ' Escríbele a EventPro para ampliarlo.'


def bloquear_si_lleno(request, recurso):
    """Respuesta de error si la agencia de quien entra ya no puede crear ese recurso; None si sí puede."""
    agencia = request.user.agencia if request.user.is_authenticated and request.user.agencia_id else None
    ok, motivo = puede_crear(agencia, recurso)
    if ok:
        return None
    if request.method == 'POST':
        registrar(Accion.LIMITE, agencia=agencia, detalle=f'{RECURSOS[recurso][1]}: {motivo}', request=request)
    return respuesta_error(request, motivo, status=403)


class LimitePlanMixin:
    """Para las vistas que crean algo con límite en el plan (recurso_limitado = 'eventos' | 'usuarios' | 'colaboradores')."""
    recurso_limitado = None

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.recurso_limitado:
            bloqueo = bloquear_si_lleno(request, self.recurso_limitado)
            if bloqueo is not None:
                return bloqueo
        return super().dispatch(request, *args, **kwargs)
