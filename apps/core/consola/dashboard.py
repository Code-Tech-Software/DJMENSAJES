"""Dashboard de EventPro: cómo va la plataforma (agencias, ingresos, uso y lo que requiere atención)."""
from collections import Counter
from datetime import datetime, time, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from apps.cuentas.models import Usuario
from apps.envivo.models import Mensaje
from apps.eventos.models import Evento
from apps.invitaciones.models import Invitado

from ..limites import uso
from ..models import Agencia, Bitacora, PagoAgencia
from . import solo_plataforma, sumar_meses

MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def _barras(valores_por_mes, hoy, meses=12):
    """Últimos `meses` meses (el actual al final) con altura relativa para el componente .bars."""
    inicio = sumar_meses(hoy.replace(day=1), -(meses - 1))
    filas = []
    for i in range(meses):
        mes = sumar_meses(inicio, i)
        filas.append({'mes': MESES[mes.month - 1], 'n': valores_por_mes.get((mes.year, mes.month), 0), 'actual': i == meses - 1})
    maximo = max((f['n'] for f in filas), default=0) or 1
    for f in filas:
        f['alto'] = round(float(f['n']) * 100 / float(maximo)) if f['n'] else 0
    return filas, inicio


def _aware(dia):
    return timezone.make_aware(datetime.combine(dia, time.min))


@solo_plataforma
def dashboard(request):
    ahora = timezone.now()
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    mes_anterior = sumar_meses(inicio_mes, -1)
    mes_siguiente = sumar_meses(inicio_mes, 1)

    agencias = list(Agencia.objects.select_related('plan').annotate(
        n_mes=Count('eventos', filter=Q(eventos__fecha_inicio_evento__gte=_aware(inicio_mes),
                                         eventos__fecha_inicio_evento__lt=_aware(mes_siguiente)), distinct=True),
    ))
    estados = Counter(a.estado for a in agencias)
    vigentes = [a for a in agencias if a.estado in ('activa', 'por_vencer')]

    # Ingresos
    pagos = PagoAgencia.objects.all()
    ingresos_mes = pagos.filter(fecha__gte=inicio_mes).aggregate(t=Sum('monto'))['t'] or 0
    ingresos_anterior = pagos.filter(fecha__gte=mes_anterior, fecha__lt=inicio_mes).aggregate(t=Sum('monto'))['t'] or 0
    variacion = round((ingresos_mes - ingresos_anterior) * 100 / ingresos_anterior) if ingresos_anterior else None
    mensual = sum((a.plan.precio_mensual for a in vigentes if a.plan_id), 0)
    por_cobrar = sorted([a for a in agencias if a.estado in ('vencida', 'por_vencer')], key=lambda a: a.vence_el)
    monto_por_cobrar = sum((a.plan.precio_mensual for a in por_cobrar if a.plan_id), 0)

    inicio_barras = sumar_meses(inicio_mes, -11)
    por_mes = {(f['m'].year, f['m'].month): f['t'] for f in pagos.filter(fecha__gte=inicio_barras)
               .annotate(m=TruncMonth('fecha')).values('m').annotate(t=Sum('monto'))}
    barras_ingresos, _ = _barras(por_mes, hoy)
    eventos_por_mes = {(f['m'].year, f['m'].month): f['n'] for f in Evento.objects.filter(fecha_inicio_evento__gte=_aware(inicio_barras))
                       .annotate(m=TruncMonth('fecha_inicio_evento')).values('m').annotate(n=Count('id'))}
    barras_eventos, _ = _barras(eventos_por_mes, hoy)

    # Uso de la plataforma
    eventos = Evento.objects.all()
    en_vivo = list(eventos.en_curso().select_related('agencia').order_by('fecha_inicio_evento')[:6])
    con_plan = [a for a in vigentes if a.plan_id]
    cerca_del_limite = []
    for a in con_plan:
        filas = [f for f in uso(a) if f['cerca']]
        if filas:
            cerca_del_limite.append({'agencia': a, 'filas': filas})

    return render(request, 'core/consola/dashboard.html', {
        'kpi': {
            'agencias_vigentes': len(vigentes), 'agencias_total': len(agencias),
            'por_vencer': estados.get('por_vencer', 0), 'vencidas': estados.get('vencida', 0), 'suspendidas': estados.get('suspendida', 0),
            'ingresos_mes': ingresos_mes, 'ingresos_anterior': ingresos_anterior, 'variacion': variacion,
            'mensual': mensual, 'monto_por_cobrar': monto_por_cobrar,
            'eventos_mes': eventos.filter(fecha_inicio_evento__gte=_aware(inicio_mes), fecha_inicio_evento__lt=_aware(mes_siguiente)).count(),
            'en_vivo': len(en_vivo),
            'usuarios': Usuario.objects.filter(is_active=True, agencia__isnull=False).count(),
            'conectados': Usuario.objects.filter(is_active=True, agencia__isnull=False, last_login__gte=ahora - timedelta(days=30)).count(),
            'invitados': Invitado.objects.count(),
            'mensajes': Mensaje.objects.exclude(tipo=Mensaje.Tipo.FOTO).count(),
            'fotos': Mensaje.objects.filter(tipo=Mensaje.Tipo.FOTO).count(),
        },
        'barras_ingresos': barras_ingresos,
        'barras_eventos': barras_eventos,
        'por_cobrar': por_cobrar[:8],
        'en_vivo': en_vivo,
        'top': sorted([a for a in agencias if a.n_mes], key=lambda a: -a.n_mes)[:5],
        'cerca_del_limite': cerca_del_limite[:6],
        'actividad': Bitacora.objects.select_related('actor', 'agencia', 'usuario')[:12],
        'hoy': hoy,
    })
