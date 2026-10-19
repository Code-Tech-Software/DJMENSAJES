"""Agencias: lista, página completa (resumen, equipo, eventos, pagos, actividad), alta y cambios."""
from collections import Counter

from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, FormView, UpdateView

from apps.cuentas.models import Usuario
from apps.envivo.models import Mensaje
from apps.eventos.models import Evento
from apps.invitaciones.models import Invitado

from ..bitacora import Accion, registrar
from ..limites import uso
from ..modulos import lista_modulos
from ..mixins import FormularioModalMixin, respuesta_ok
from ..models import Agencia, Ajustes, Plan
from . import PlataformaMixin, clave_temporal, recordar_acceso, slug_para, solo_plataforma, sumar_meses, tomar_acceso
from .forms import AdministradorForm, AgenciaForm, AgenciaNuevaForm

EXTENSIONES = {'1': (1, '1 mes'), '3': (3, '3 meses'), '12': (12, '1 año')}


def crear_administrador(agencia, datos):
    clave = datos.get('admin_clave') or clave_temporal()
    nombre = datos['admin_nombre'].strip()
    usuario = Usuario.objects.create_user(
        username=datos['admin_usuario'], password=clave, email=datos.get('admin_correo', ''),
        first_name=nombre.split(' ', 1)[0], last_name=nombre.split(' ', 1)[1] if ' ' in nombre else '',
        agencia=agencia, rol=Usuario.Rol.ADMIN,
    )
    return usuario, clave


@solo_plataforma
def agencias(request):
    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    plan = request.GET.get('plan', '')
    ahora = timezone.now()
    lista = Agencia.objects.select_related('plan').annotate(
        n_eventos=Count('eventos', distinct=True),
        n_proximos=Count('eventos', filter=Q(eventos__fecha_inicio_evento__gt=ahora), distinct=True),
        n_usuarios=Count('usuarios', filter=Q(usuarios__is_active=True), distinct=True),
        ultimo_acceso=Max('usuarios__last_login'),
    ).order_by('nombre')
    if q:
        lista = lista.filter(Q(nombre__icontains=q) | Q(notas__icontains=q) | Q(usuarios__username__icontains=q)).distinct()
    if plan == 'sin':
        lista = lista.filter(plan__isnull=True)
    elif plan.isdigit():
        lista = lista.filter(plan_id=plan)
    todas = list(lista)
    conteo = Counter(a.estado for a in todas)
    if estado in Agencia.ESTADOS:
        todas = [a for a in todas if a.estado == estado]
    return render(request, 'core/consola/agencias.html', {
        'agencias': todas, 'conteo': conteo, 'total': sum(conteo.values()),
        'q': q, 'estado': estado, 'plan': plan, 'estados': Agencia.ESTADOS, 'planes': Plan.objects.all(),
    })


@solo_plataforma
def agencia(request, pk):
    agencia = get_object_or_404(Agencia.objects.select_related('plan'), pk=pk)
    ahora = timezone.now()
    hoy = timezone.localdate()
    eventos = Evento.objects.filter(agencia=agencia)
    return render(request, 'core/consola/agencia.html', {
        'agencia': agencia,
        'acceso': tomar_acceso(request, f'agencia:{agencia.pk}'),
        'equipo': agencia.usuarios.select_related('colaborador').order_by('-is_active', 'rol', 'first_name', 'username'),
        'eventos': eventos.select_related('colaborador').annotate(
            n_invitados=Count('invitados', distinct=True), n_mensajes=Count('mensajes', distinct=True),
        ).order_by('-fecha_inicio_evento')[:60],
        'pagos': agencia.pagos.select_related('registrado_por')[:60],
        'actividad': agencia.bitacora.select_related('actor', 'usuario')[:60],
        'uso': uso(agencia),
        'modulos': lista_modulos(agencia),
        'ajustes': Ajustes.de(agencia),
        'stats': {
            'eventos': eventos.count(),
            'proximos': eventos.filter(fecha_inicio_evento__gt=ahora).count(),
            'este_mes': eventos.filter(fecha_inicio_evento__year=hoy.year, fecha_inicio_evento__month=hoy.month).count(),
            'invitados': Invitado.objects.filter(evento__agencia=agencia).count(),
            'mensajes': Mensaje.objects.filter(evento__agencia=agencia).count(),
            'colaboradores': agencia.colaboradores.count(),
            'pagado': sum((p.monto for p in agencia.pagos.all()), 0),
        },
        'extensiones': EXTENSIONES,
    })


class AgenciaCrear(PlataformaMixin, FormularioModalMixin, CreateView):
    model = Agencia
    form_class = AgenciaNuevaForm
    template_modal = 'core/consola/form_agencia.html'
    titulo = 'Nueva agencia'
    subtitulo = 'Crea la agencia y el acceso de su administrador.'
    icono = 'ph ph-buildings'
    tamano = 'lg'
    texto_boton = 'Crear agencia'

    def get_initial(self):
        return {**super().get_initial(), 'vence_el': sumar_meses(timezone.localdate(), 1)}

    def form_valid(self, form):
        with transaction.atomic():
            agencia = form.save(commit=False)
            agencia.slug = slug_para(agencia.nombre)
            agencia.save()
            usuario, clave = crear_administrador(agencia, form.cleaned_data)
        Ajustes.de(agencia)  # sus ajustes nacen con su nombre
        registrar(Accion.AGENCIA_CREADA, agencia=agencia, detalle=f'Plan: {agencia.plan or "sin plan"}', request=self.request)
        registrar(Accion.USUARIO_CREADO, usuario=usuario, detalle=f'@{usuario.username} · administrador', request=self.request)
        recordar_acceso(self.request, usuario, clave, f'agencia:{agencia.pk}')
        return respuesta_ok(self.request, f'Agencia "{agencia.nombre}" creada.', redirect=reverse('plataforma:agencia', args=[agencia.pk]))


class AgenciaEditar(PlataformaMixin, FormularioModalMixin, UpdateView):
    model = Agencia
    form_class = AgenciaForm
    template_modal = 'core/consola/form_agencia_editar.html'
    titulo = 'Editar agencia'
    icono = 'ph ph-buildings'
    mensaje_exito = 'Agencia actualizada.'

    def get_subtitulo(self):
        return self.object.nombre

    def form_valid(self, form):
        cambios = ', '.join(form.fields[c].label or c for c in form.changed_data)
        respuesta = super().form_valid(form)
        if cambios:
            registrar(Accion.AGENCIA_EDITADA, agencia=self.object, detalle=f'Cambió: {cambios}', request=self.request)
        return respuesta


class AdministradorCrear(PlataformaMixin, FormularioModalMixin, FormView):
    form_class = AdministradorForm
    template_modal = 'core/consola/form_administrador.html'
    titulo = 'Nuevo administrador'
    icono = 'ph ph-user-plus'
    texto_boton = 'Crear acceso'

    def dispatch(self, request, *args, **kwargs):
        self.agencia = get_object_or_404(Agencia, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_subtitulo(self):
        return self.agencia.nombre

    def form_valid(self, form):
        usuario, clave = crear_administrador(self.agencia, form.cleaned_data)
        registrar(Accion.USUARIO_CREADO, usuario=usuario, detalle=f'@{usuario.username} · administrador', request=self.request)
        recordar_acceso(self.request, usuario, clave, f'agencia:{self.agencia.pk}')
        return respuesta_ok(self.request, 'Acceso creado.', redirect=reverse('plataforma:agencia', args=[self.agencia.pk]))


@solo_plataforma
@require_POST
def extender(request, pk, meses):
    """Extiende la vigencia sin registrar un pago (cortesía, ajuste)."""
    agencia = get_object_or_404(Agencia, pk=pk)
    if meses not in EXTENSIONES:
        raise Http404
    hoy = timezone.localdate()
    base = agencia.vence_el if agencia.vence_el and agencia.vence_el >= hoy else hoy
    agencia.vence_el = sumar_meses(base, EXTENSIONES[meses][0])
    agencia.save(update_fields=['vence_el'])
    registrar(Accion.VIGENCIA, agencia=agencia, detalle=f'+{EXTENSIONES[meses][1]} sin pago · vence {agencia.vence_el:%d/%m/%Y}', request=request)
    return respuesta_ok(request, f'Extendida {EXTENSIONES[meses][1]}: ahora vence el {agencia.vence_el:%d/%m/%Y}.')


@solo_plataforma
@require_POST
def suspender(request, pk):
    agencia = get_object_or_404(Agencia, pk=pk)
    agencia.activa = not agencia.activa
    agencia.save(update_fields=['activa'])
    registrar(Accion.AGENCIA_REACTIVADA if agencia.activa else Accion.AGENCIA_SUSPENDIDA, agencia=agencia, request=request)
    return respuesta_ok(request, f'{agencia.nombre} ' + ('reactivada: su equipo ya puede entrar.' if agencia.activa
                                                         else 'suspendida: su equipo ya no puede entrar al panel.'))
