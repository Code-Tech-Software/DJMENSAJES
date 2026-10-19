"""Pagos de las agencias (cobro manual): registrar uno extiende el vencimiento de la agencia."""
from datetime import date

from django.db.models import Sum
from django.db.models.functions import ExtractYear
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from ..bitacora import Accion, registrar
from ..mixins import FormularioModalMixin, respuesta_ok
from ..models import Agencia, PagoAgencia
from . import PlataformaMixin, solo_plataforma, sumar_meses
from .forms import PagoForm


def aplicar_pago(pago, reactivar=True):
    """Extiende la vigencia de la agencia los meses pagados (desde su vencimiento, o desde hoy si ya venció)."""
    agencia = pago.agencia
    hoy = timezone.localdate()
    base = agencia.vence_el if agencia.vence_el and agencia.vence_el >= hoy else hoy
    agencia.vence_el = sumar_meses(base, pago.meses)
    campos = ['vence_el']
    if reactivar and not agencia.activa:
        agencia.activa = True
        campos.append('activa')
    agencia.save(update_fields=campos)
    pago.cubre_hasta = agencia.vence_el


@solo_plataforma
def pagos(request):
    hoy = timezone.localdate()
    agencia = request.GET.get('agencia', '')
    anio = request.GET.get('anio', '')
    lista = PagoAgencia.objects.select_related('agencia', 'registrado_por')
    if agencia.isdigit():
        lista = lista.filter(agencia_id=agencia)
    if anio.isdigit():
        lista = lista.filter(fecha__year=int(anio))
    todos = PagoAgencia.objects.all()
    inicio_mes = hoy.replace(day=1)
    return render(request, 'core/consola/pagos.html', {
        'pagos': lista[:300], 'suma_filtro': lista.aggregate(t=Sum('monto'))['t'] or 0, 'n_filtro': lista.count(),
        'agencia': agencia, 'anio': anio, 'agencias': Agencia.objects.order_by('nombre'),
        'anios': sorted({a for a in todos.annotate(a=ExtractYear('fecha')).values_list('a', flat=True)}, reverse=True),
        'totales': {
            'mes': todos.filter(fecha__gte=inicio_mes).aggregate(t=Sum('monto'))['t'] or 0,
            'mes_anterior': todos.filter(fecha__gte=sumar_meses(inicio_mes, -1), fecha__lt=inicio_mes).aggregate(t=Sum('monto'))['t'] or 0,
            'anio': todos.filter(fecha__gte=date(hoy.year, 1, 1)).aggregate(t=Sum('monto'))['t'] or 0,
            'total': todos.aggregate(t=Sum('monto'))['t'] or 0,
        },
    })


class PagoCrear(PlataformaMixin, FormularioModalMixin, CreateView):
    model = PagoAgencia
    form_class = PagoForm
    template_modal = 'core/consola/form_pago.html'
    titulo = 'Registrar pago'
    subtitulo = 'Extiende el vencimiento de la agencia los meses que cubre.'
    icono = 'ph ph-hand-coins'
    texto_boton = 'Registrar pago'

    def dispatch(self, request, *args, **kwargs):
        self.agencia = get_object_or_404(Agencia.objects.select_related('plan'), pk=kwargs['pk']) if 'pk' in kwargs else None
        return super().dispatch(request, *args, **kwargs)

    def get_subtitulo(self):
        return self.agencia.nombre if self.agencia else self.subtitulo

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'agencia': self.agencia}

    def form_valid(self, form):
        pago = form.save(commit=False)
        if self.agencia is not None:
            pago.agencia = self.agencia
        pago.registrado_por = self.request.user
        aplicar_pago(pago, reactivar=form.cleaned_data.get('reactivar'))
        pago.save()
        registrar(Accion.PAGO, agencia=pago.agencia,
                  detalle=f'${pago.monto:,.2f} · {pago.meses} mes{"es" if pago.meses != 1 else ""} · cubre hasta {pago.cubre_hasta:%d/%m/%Y}',
                  request=self.request)
        destino = reverse('plataforma:agencia', args=[pago.agencia_id]) + '#pagos' if self.agencia else reverse('plataforma:pagos')
        return respuesta_ok(self.request, f'Pago registrado: {pago.agencia} queda vigente hasta el {pago.cubre_hasta:%d/%m/%Y}.', redirect=destino)


@solo_plataforma
@require_POST
def eliminar(request, pk):
    """Borra un pago registrado por error. No cambia el vencimiento (se ajusta a mano si hace falta)."""
    pago = get_object_or_404(PagoAgencia.objects.select_related('agencia'), pk=pk)
    registrar(Accion.PAGO_ELIMINADO, agencia=pago.agencia, detalle=f'${pago.monto:,.2f} del {pago.fecha:%d/%m/%Y}', request=request)
    pago.delete()
    return respuesta_ok(request, 'Pago eliminado. El vencimiento de la agencia no cambió; ajústalo desde Editar si hace falta.')
