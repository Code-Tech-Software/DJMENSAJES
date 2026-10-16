from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from apps.core.mixins import FormularioModalMixin, respuesta_ok
from apps.cuentas.permisos import CatalogosRequeridoMixin, catalogos_requerido

from .forms import ColaboradorForm
from .models import Colaborador


@catalogos_requerido
def lista(request):
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '')
    estado = request.GET.get('estado', '')
    ahora = timezone.now()
    colaboradores = Colaborador.objects.annotate(
        n_eventos=Count('eventos', distinct=True),
        n_proximos=Count('eventos', filter=Q(eventos__fecha_inicio_evento__gt=ahora), distinct=True),
        n_usuarios=Count('usuarios', distinct=True),
    ).order_by('-estado', 'nombre')
    if q:
        colaboradores = colaboradores.filter(Q(nombre__icontains=q) | Q(ciudad__icontains=q) | Q(responsable__icontains=q))
    if tipo:
        colaboradores = colaboradores.filter(tipo=tipo)
    if estado in ('1', '0'):
        colaboradores = colaboradores.filter(estado=estado == '1')
    return render(request, 'colaboradores/lista.html', {
        'colaboradores': colaboradores, 'q': q, 'tipo': tipo, 'estado': estado,
        'tipos': Colaborador.Tipo.choices,
        'total': Colaborador.objects.count(),
        'activos': Colaborador.objects.filter(estado=True).count(),
    })


@login_required
def detalle(request, pk):
    colaborador = get_object_or_404(Colaborador, pk=pk)
    if not (request.user.ve_todo or request.user.colaborador_id == colaborador.pk):
        raise PermissionDenied
    ahora = timezone.now()
    eventos = colaborador.eventos.all()
    return render(request, 'colaboradores/detalle.html', {
        'colaborador': colaborador,
        'proximos': eventos.filter(fecha_inicio_evento__gt=ahora).order_by('fecha_inicio_evento')[:6],
        'recientes': eventos.filter(fecha_inicio_evento__lte=ahora).order_by('-fecha_inicio_evento')[:5],
        'equipo': colaborador.usuarios.all(),
        'stats': {
            'total': eventos.count(),
            'proximos': eventos.filter(fecha_inicio_evento__gt=ahora).count(),
            'este_anio': eventos.filter(fecha_inicio_evento__year=timezone.localdate().year).count(),
            'mensajes': colaborador.eventos.aggregate(n=Count('mensajes'))['n'],
        },
        'puede_editar': request.user.ve_todo,
    })


class ColaboradorCrear(CatalogosRequeridoMixin, FormularioModalMixin, CreateView):
    model = Colaborador
    form_class = ColaboradorForm
    template_modal = 'colaboradores/partials/form.html'
    titulo = 'Nuevo colaborador'
    subtitulo = 'Registra una sub-agencia o proveedor aliado.'
    icono = 'ri-team-line'
    tamano = 'lg'
    texto_boton = 'Registrar'
    mensaje_exito = 'Colaborador registrado.'


class ColaboradorEditar(CatalogosRequeridoMixin, FormularioModalMixin, UpdateView):
    model = Colaborador
    form_class = ColaboradorForm
    template_modal = 'colaboradores/partials/form.html'
    titulo = 'Editar colaborador'
    icono = 'ri-team-line'
    tamano = 'lg'
    mensaje_exito = 'Colaborador actualizado.'

    def get_subtitulo(self):
        return self.object.nombre


@catalogos_requerido
@require_POST
def eliminar(request, pk):
    colaborador = get_object_or_404(Colaborador, pk=pk)
    nombre = colaborador.nombre
    colaborador.delete()
    return respuesta_ok(request, f'Se eliminó a {nombre}. Sus eventos se conservan sin agencia asignada.',
                        redirect=reverse('colaboradores:lista'))
