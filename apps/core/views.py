from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.colaboradores.models import Colaborador
from apps.core.actividad import actividad_reciente, recordatorios
from apps.core.forms import AjustesForm
from apps.core.limites import uso
from apps.core.modulos import lista_modulos
from apps.core.models import Ajustes
from apps.cuentas.models import Usuario
from apps.envivo.models import Mensaje
from apps.eventos.models import ICONOS_TIPO, Evento, Pago, TipoEvento
from apps.invitaciones.models import Invitado

MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


@login_required
def dashboard(request):
    if request.user.is_superuser and not request.user.agencia_id:
        return redirect('plataforma:dashboard')  # cuenta de EventPro sin agencia propia: su consola
    ahora = timezone.now()
    hoy = timezone.localdate()
    eventos = Evento.objects.visibles_para(request.user)
    vigentes = eventos.vigentes()

    proximos_30 = vigentes.filter(fecha_inicio_evento__gt=ahora, fecha_inicio_evento__lte=ahora + timedelta(days=30))
    este_mes = vigentes.filter(fecha_inicio_evento__year=hoy.year, fecha_inicio_evento__month=hoy.month)
    futuros = vigentes.filter(fecha_fin_evento__gte=ahora)

    invitados = Invitado.objects.filter(evento__in=futuros).aggregate(
        pases=Sum('pases'),
        confirmados=Sum('pases_confirmados', filter=Q(estado='confirmado')),
        pendientes=Count('id', filter=Q(estado='pendiente')),
    )
    mensajes = Mensaje.objects.filter(evento__in=eventos, fecha_creacion__gte=ahora - timedelta(days=30)).aggregate(
        total=Count('id'),
        canciones=Count('id', filter=Q(tipo='cancion')),
    )

    # Para planes sin invitaciones o sin experiencia en vivo, el dashboard muestra datos de agenda
    cotizaciones = futuros.filter(etapa=Evento.Etapa.COTIZACION).count()
    invitados_estimados = proximos_30.aggregate(t=Sum('num_invitados'))['t'] or 0

    por_cobrar = None
    if request.user.ve_todo:
        confirmados = futuros.filter(etapa=Evento.Etapa.CONFIRMADO)
        total = confirmados.aggregate(t=Sum('precio_total'))['t'] or 0
        pagado = Pago.objects.filter(evento__in=confirmados).aggregate(t=Sum('monto'))['t'] or 0
        por_cobrar = max(total - pagado, 0)

    en_curso = list(vigentes.en_curso().select_related('banner', 'colaborador')[:3])
    agenda = list(vigentes.proximos().select_related('banner', 'colaborador').order_by('fecha_inicio_evento')[:6])
    destacado = en_curso[0] if en_curso else (agenda[0] if agenda else None)

    # Barras: eventos por mes del año en curso
    por_mes = dict(
        vigentes.filter(fecha_inicio_evento__year=hoy.year)
        .values_list('fecha_inicio_evento__month').annotate(n=Count('id'))
    )
    maximo = max(por_mes.values(), default=0) or 1
    barras = [{
        'mes': MESES[m - 1],
        'n': por_mes.get(m, 0),
        'alto': round(por_mes.get(m, 0) * 100 / maximo),
        'actual': m == hoy.month,
    } for m in range(1, 13)]

    # Dona: distribución por tipo
    por_tipo = list(vigentes.values('tipo_evento').annotate(n=Count('id')).order_by('-n'))
    total_tipos = sum(t['n'] for t in por_tipo) or 0
    etiquetas = dict(TipoEvento.choices)
    acumulado, segmentos = 0, []
    for item in por_tipo:
        inicio = acumulado
        acumulado += item['n'] * 100 / (total_tipos or 1)
        segmentos.append({
            'tipo': item['tipo_evento'],
            'nombre': etiquetas.get(item['tipo_evento'], 'Otro'),
            'n': item['n'],
            'inicio': round(inicio, 2),
            'fin': round(acumulado, 2),
        })
    gradiente = ', '.join(f"var(--t-{s['tipo']}) {s['inicio']}% {s['fin']}%" for s in segmentos)

    return render(request, 'core/dashboard.html', {
        'stats': {
            'proximos_30': proximos_30.count(),
            'este_mes': este_mes.count(),
            'pases': invitados['pases'] or 0,
            'confirmados': invitados['confirmados'] or 0,
            'pendientes_rsvp': invitados['pendientes'] or 0,
            'mensajes': mensajes['total'],
            'canciones': mensajes['canciones'],
            'por_cobrar': por_cobrar,
            'total_eventos': eventos.count(),
            'cotizaciones': cotizaciones,
            'invitados_estimados': invitados_estimados,
        },
        'destacado': destacado,
        'en_curso': en_curso,
        'agenda': agenda,
        'barras': barras,
        'anio': hoy.year,
        'segmentos': segmentos,
        'gradiente': gradiente,
        'total_tipos': total_tipos,
        'actividad': actividad_reciente(request.user, limite=8),
        'recordatorios': recordatorios(request.user),
    })


@login_required
def buscar(request):
    q = request.GET.get('q', '').strip()
    grupos = []
    if len(q) >= 2:
        eventos = (Evento.objects.visibles_para(request.user)
                   .filter(Q(nombre_evento__icontains=q) | Q(lugar__icontains=q) | Q(cliente_nombre__icontains=q))
                   .order_by('-fecha_inicio_evento')[:6])
        grupos.append({'grupo': 'Eventos', 'items': [{
            'titulo': e.nombre_evento,
            'sub': f"{e.tipo_corto} · {timezone.localtime(e.fecha_inicio_evento):%d/%m/%Y}" + (f' · {e.lugar}' if e.lugar else ''),
            'url': e.get_absolute_url(),
            'icono': ICONOS_TIPO.get(e.tipo_evento, 'ph ph-calendar-dots'),
            'color': f'var(--t-{e.tipo_evento})',
        } for e in eventos]})

        invitados = (Invitado.objects.filter(evento__in=Evento.objects.visibles_para(request.user), nombre__icontains=q)
                     .select_related('evento')[:6])
        grupos.append({'grupo': 'Invitados', 'items': [{
            'titulo': i.nombre,
            'sub': f'{i.evento.nombre_evento} · {i.get_estado_display()} · {i.pases} pase(s)',
            'url': f"{reverse('invitaciones:panel', args=[i.evento_id])}?{urlencode({'q': i.nombre})}",
            'icono': 'ph ph-user-list',
        } for i in invitados]})

        if request.user.ve_todo:
            colaboradores = (Colaborador.objects.filter(agencia_id=request.user.agencia_id)
                             .filter(Q(nombre__icontains=q) | Q(ciudad__icontains=q))[:4])
            grupos.append({'grupo': 'Colaboradores', 'items': [{
                'titulo': c.nombre, 'sub': c.get_tipo_display(), 'url': c.get_absolute_url(), 'icono': 'ph ph-users-three',
            } for c in colaboradores]})
        if request.user.es_admin:
            usuarios = Usuario.objects.filter(agencia_id=request.user.agencia_id).filter(
                Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))[:4]
            grupos.append({'grupo': 'Equipo', 'items': [{
                'titulo': str(u), 'sub': f'@{u.username} · {u.rol_visible}', 'url': reverse('cuentas:usuarios'), 'icono': 'ph ph-shield-check',
            } for u in usuarios]})
    return JsonResponse({'grupos': [g for g in grupos if g['items']]})


@login_required
def notificaciones(request):
    return render(request, 'core/partials/notificaciones.html', {
        'actividad': actividad_reciente(request.user, limite=12),
        'recordatorios': recordatorios(request.user),
        'vistas_en': request.user.notificaciones_vistas_en,
    })


@login_required
@require_POST
def notificaciones_leidas(request):
    request.user.notificaciones_vistas_en = timezone.now()
    request.user.save(update_fields=['notificaciones_vistas_en'])
    return JsonResponse({'ok': True})


def error_403(request, exception=None):
    return render(request, 'errores/error.html', {
        'codigo': 403, 'titulo': 'Acceso restringido',
        'texto': 'Tu rol no tiene permiso para ver esta sección. Si crees que es un error, contacta a un administrador.',
        'icono': 'ph ph-lock',
    }, status=403)


def error_404(request, exception=None):
    return render(request, 'errores/error.html', {
        'codigo': 404, 'titulo': 'Página no encontrada',
        'texto': 'El enlace que abriste no existe o ya no está disponible.',
        'icono': 'ph ph-compass',
    }, status=404)


def error_500(request):
    return render(request, 'errores/error.html', {
        'codigo': 500, 'titulo': 'Algo salió mal',
        'texto': 'Tuvimos un problema al procesar tu solicitud. Intenta de nuevo en unos momentos.',
        'icono': 'ph ph-wrench',
    }, status=500)


@login_required
def ajustes(request):
    """Ajustes de la plataforma.

    Todos ajustan la apariencia (se guarda en su dispositivo). Los administradores además
    editan la marca del negocio y los valores con los que nacen los eventos e invitaciones.
    """
    form = None
    seccion = 'apariencia'
    if request.user.es_admin and request.user.agencia_id:
        form = AjustesForm(request.POST or None, request.FILES or None, instance=Ajustes.de(request.user.agencia_id))
        if request.method == 'POST':
            if form.is_valid():
                form.save()
                messages.success(request, 'Ajustes guardados.')
                destino = request.POST.get('seccion') if request.POST.get('seccion') in ('negocio', 'eventos') else 'negocio'
                return redirect(f"{reverse('core:ajustes')}#{destino}")
            # Abre la pestaña donde está el primer error
            seccion = 'eventos' if set(form.errors) & set(SECCION_EVENTOS) else 'negocio'
    elif request.method == 'POST':
        messages.error(request, 'Solo un administrador puede cambiar los ajustes del negocio.')
        return redirect('core:ajustes')
    mi_plan = None
    if request.user.es_admin and request.user.agencia_id:
        agencia = request.user.agencia
        mi_plan = {'agencia': agencia, 'uso': uso(agencia), 'modulos': lista_modulos(agencia), 'contacto': Ajustes.plataforma()}
    return render(request, 'core/ajustes.html', {'form': form, 'seccion_activa': seccion, 'mi_plan': mi_plan})


SECCION_EVENTOS = ('cooldown', 'permitir_saludos', 'permitir_canciones', 'permitir_fotos', 'moderar_pantalla',
                   'mensaje_bienvenida', 'plantilla', 'dias_limite_rsvp')
