"""Planes: precio de referencia, capacidad (eventos al mes, usuarios) y qué incluyen (módulos, fotos, sub-agencias)."""
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from ..bitacora import Accion, registrar
from ..mixins import FormularioModalMixin, respuesta_error, respuesta_ok
from ..models import Agencia, Plan
from ..modulos import MODULOS, lista_modulos
from . import PlataformaMixin, solo_plataforma
from .forms import PlanForm


@solo_plataforma
def planes(request):
    lista = list(Plan.objects.annotate(
        n_agencias=Count('agencias', distinct=True),
        n_activas=Count('agencias', filter=Q(agencias__activa=True), distinct=True),
    ).order_by(*Plan._meta.ordering))  # con conteos Django no aplica el orden del modelo
    for plan in lista:
        plan.modulos = lista_modulos(Agencia(plan=plan))
        plan.n_incluidos = sum(m['incluido'] for m in plan.modulos) + (plan.max_colaboradores != 0)
        plan.con_fotos_invitados = next(m['incluido'] for m in plan.modulos if m['clave'] == 'fotos')
    return render(request, 'core/consola/planes.html', {
        'planes': lista, 'sin_plan': Agencia.objects.filter(plan__isnull=True).count(), 'n_modulos': len(MODULOS) + 1,
    })


class PlanFormMixin(PlataformaMixin, FormularioModalMixin):
    model = Plan
    form_class = PlanForm
    template_modal = 'core/consola/form_plan.html'
    icono = 'ph ph-stack'
    tamano = 'lg'

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        registrar(Accion.PLAN, detalle=f'{self.object.nombre} · ${self.object.precio_mensual:,.0f}/mes', request=self.request)
        return respuesta


class PlanCrear(PlanFormMixin, CreateView):
    titulo = 'Nuevo plan'
    subtitulo = 'Elige su capacidad y qué secciones incluye.'
    texto_boton = 'Crear plan'
    mensaje_exito = 'Plan creado.'


class PlanEditar(PlanFormMixin, UpdateView):
    titulo = 'Editar plan'
    mensaje_exito = 'Plan actualizado. Los límites aplican desde ahora a sus agencias.'

    def get_subtitulo(self):
        return self.object.nombre


@solo_plataforma
@require_POST
def eliminar(request, pk):
    plan = get_object_or_404(Plan, pk=pk)
    if plan.agencias.exists():
        return respuesta_error(request, f'{plan.agencias.count()} agencia(s) usan este plan. Cámbialas de plan o desactívalo en lugar de borrarlo.')
    registrar(Accion.PLAN, detalle=f'{plan.nombre} eliminado', request=request)
    plan.delete()
    return respuesta_ok(request, 'Plan eliminado.')
