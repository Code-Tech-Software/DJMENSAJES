"""Directorio de clientes: lista con su historial, ficha de cada cliente, alta, edición, fusión y exportación."""
import csv
import re
from urllib.parse import quote, urlencode

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, FormView, UpdateView

from apps.core.mixins import AsignarAgenciaMixin, FormularioModalMixin, respuesta_ok

from ..models import Cliente, Cotizacion, Evento
from .forms import ClienteForm, FusionarForm
from .servicios import actualizar_contacto, con_resumen, fusionar


def clientes_de(usuario):
    return Cliente.objects.visibles_para(usuario)


def obtener(request, pk):
    return get_object_or_404(con_resumen(clientes_de(request.user), request.user), pk=pk)


def _gestiona(usuario):
    """Fusionar, eliminar y exportar: administradores y coordinadores."""
    return usuario.is_authenticated and usuario.agencia_id and usuario.ve_todo


# --- Lista ------------------------------------------------------------------------------------------

FILTROS = (
    ('', 'Todos', 'ph ph-address-book'),
    ('proximos', 'Con evento próximo', 'ph ph-calendar-check'),
    ('saldo', 'Con saldo', 'ph ph-wallet'),
    ('frecuentes', 'Frecuentes', 'ph ph-star'),
    ('prospectos', 'Prospectos', 'ph ph-user-focus'),
)
FILTRO = {
    'proximos': Q(proximo__isnull=False),
    'saldo': Q(saldo__gt=0),
    'frecuentes': Q(n_confirmados__gte=2),
    'prospectos': Q(n_confirmados=0),
}
ORDENES = (
    ('recientes', 'Actividad reciente', ('-actualizado', 'nombre')),
    ('nombre', 'Nombre', ('nombre',)),
    ('contratado', 'Mayor importe', ('-contratado', 'nombre')),
    ('saldo', 'Mayor saldo', ('-saldo', 'nombre')),
)


def _buscar(clientes, q):
    filtro = Q(nombre__icontains=q) | Q(email__icontains=q)
    digitos = re.sub(r'\D', '', q)
    if len(digitos) >= 3:
        filtro |= Q(telefono_normalizado__contains=digitos)
    return clientes.filter(filtro)


@login_required
def lista(request):
    base = con_resumen(clientes_de(request.user), request.user)
    filtro = request.GET.get('filtro', '')
    filtro = filtro if filtro in FILTRO else ''
    orden = request.GET.get('orden', 'recientes')
    campos_orden = dict((clave, campos) for clave, _, campos in ORDENES).get(orden)
    if campos_orden is None:
        orden, campos_orden = 'recientes', ORDENES[0][2]
    q = request.GET.get('q', '').strip()

    # Números del directorio (en Python: son pocos cientos por agencia y así se suman los subtotales anotados)
    filas = list(base.values_list('creado', 'proximo', 'saldo', 'n_confirmados'))
    inicio_mes = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    con_compra = sum(1 for f in filas if f[3] >= 1)
    frecuentes = sum(1 for f in filas if f[3] >= 2)
    conteos = {
        '': len(filas),
        'proximos': sum(1 for f in filas if f[1]),
        'saldo': sum(1 for f in filas if f[2] > 0),
        'frecuentes': frecuentes,
        'prospectos': sum(1 for f in filas if f[3] == 0),
    }
    stats = {
        'total': len(filas),
        'nuevos_mes': sum(1 for f in filas if f[0] >= inicio_mes),
        'con_proximo': conteos['proximos'],
        'por_cobrar': sum((f[2] for f in filas if f[2] > 0), 0),
        'con_saldo': conteos['saldo'],
        'frecuentes': frecuentes,
        'recompra': round(frecuentes * 100 / con_compra) if con_compra else None,
    }

    clientes = base.filter(FILTRO.get(filtro, Q()))
    if q:
        clientes = _buscar(clientes, q)
    pagina = Paginator(clientes.order_by(*campos_orden), 30).get_page(request.GET.get('page'))
    query = urlencode({k: v for k, v in (('filtro', filtro), ('q', q), ('orden', orden if orden != 'recientes' else '')) if v})
    return render(request, 'clientes/lista.html', {
        'pagina': pagina, 'clientes': pagina.object_list, 'query': query, 'stats': stats, 'q': q,
        'filtro': filtro, 'orden': orden, 'ordenes': [(clave, nombre) for clave, nombre, _ in ORDENES],
        'filtros': [(clave, nombre, icono, conteos[clave]) for clave, nombre, icono in FILTROS],
        'gestiona': _gestiona(request.user),
    })


# --- Ficha del cliente ----------------------------------------------------------------------------------

@login_required
def detalle(request, pk):
    cliente = obtener(request, pk)
    ahora = timezone.now()
    eventos = list(Evento.objects.visibles_para(request.user).filter(cliente=cliente)
                   .select_related('colaborador').annotate(pagado_total=Sum('pagos__monto')).order_by('-fecha_inicio_evento'))
    for e in eventos:
        e._total_pagado = e.pagado_total or 0  # evita una consulta por evento
    proximos = sorted((e for e in eventos if e.fecha_fin_evento >= ahora and e.etapa != Evento.Etapa.CANCELADO),
                      key=lambda e: e.fecha_inicio_evento)
    historial = [e for e in eventos if e not in proximos]
    cotizaciones = (Cotizacion.objects.visibles_para(request.user).filter(cliente=cliente)
                    .select_related('evento').prefetch_related('conceptos').order_by('-creado'))
    texto = f'Hola {cliente.nombre.split(" ")[0]}, '
    return render(request, 'clientes/detalle.html', {
        'cliente': cliente, 'proximos': proximos, 'historial': historial, 'cotizaciones': cotizaciones,
        'n_eventos_total': len(eventos),
        'url_whatsapp': f'https://wa.me/{cliente.whatsapp}?text={quote(texto)}' if cliente.whatsapp else '',
        'pagado_pct': min(100, int(cliente.pagado * 100 / cliente.contratado)) if cliente.contratado else 0,
        'gestiona': _gestiona(request.user),
    })


# --- Alta, edición, fusión y baja ----------------------------------------------------------------------

class ClienteFormMixin(LoginRequiredMixin, FormularioModalMixin):
    model = Cliente
    form_class = ClienteForm
    template_modal = 'clientes/form_cliente.html'
    icono = 'ph ph-address-book'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['usuario'] = self.request.user
        return kwargs


class ClienteCrear(AsignarAgenciaMixin, ClienteFormMixin, CreateView):
    titulo = 'Nuevo cliente'
    subtitulo = 'Agrégalo a tu directorio; sus eventos y cotizaciones se juntan en su ficha.'
    texto_boton = 'Agregar cliente'

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        return super().form_valid(form)

    def get_mensaje_exito(self):
        return f'{self.object.nombre} se agregó a tu directorio.'

    def get_url_exito(self):
        return super().get_url_exito() or self.object.get_absolute_url()


class ClienteEditar(ClienteFormMixin, UpdateView):
    titulo = 'Editar cliente'
    texto_boton = 'Guardar cambios'

    def get_queryset(self):
        return clientes_de(self.request.user)

    def get_subtitulo(self):
        return 'Si cambias su nombre, teléfono o correo, también se corrigen en sus eventos próximos y cotizaciones abiertas.'

    def form_valid(self, form):
        antes = Cliente.objects.values('nombre', 'telefono', 'email').get(pk=self.object.pk)
        self.object = form.save()
        self.actualizados = actualizar_contacto(self.object, antes)
        return self.respuesta_exito()

    def get_mensaje_exito(self):
        n = self.actualizados
        return 'Cliente actualizado' + (f' (y sus datos en {n} evento{"s" if n != 1 else ""} o cotizaci{"ones" if n != 1 else "ón"} en curso).' if n else '.')


class Fusionar(LoginRequiredMixin, FormularioModalMixin, FormView):
    form_class = FusionarForm
    template_modal = 'clientes/form_fusionar.html'
    icono = 'ph ph-git-merge'
    titulo = 'Juntar fichas duplicadas'
    texto_boton = 'Juntar fichas'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not _gestiona(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_cliente(self):
        if not hasattr(self, '_cliente'):
            self._cliente = get_object_or_404(clientes_de(self.request.user), pk=self.kwargs['pk'])
        return self._cliente

    def get_subtitulo(self):
        return self.get_cliente().nombre

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'cliente': self.get_cliente(), 'usuario': self.request.user}

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'cliente': self.get_cliente()}

    def form_valid(self, form):
        duplicado = form.cleaned_data['duplicado']
        nombre = duplicado.nombre
        cliente = fusionar(self.get_cliente(), duplicado)
        return respuesta_ok(self.request, f'Listo: «{nombre}» quedó dentro de la ficha de {cliente.nombre}.',
                            redirect=cliente.get_absolute_url())


@login_required
@require_POST
def eliminar(request, pk):
    if not _gestiona(request.user):
        raise PermissionDenied
    cliente = get_object_or_404(clientes_de(request.user), pk=pk)
    nombre = cliente.nombre
    cliente.delete()  # sus eventos y cotizaciones se quedan (con los datos del cliente tal como se guardaron)
    return respuesta_ok(request, f'{nombre} se quitó del directorio. Sus eventos y cotizaciones no cambian.',
                        redirect=reverse('clientes:lista'))


@login_required
def exportar(request):
    """El directorio en CSV (se abre en Excel) con el historial de cada cliente."""
    if not _gestiona(request.user):
        raise PermissionDenied
    respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
    respuesta['Content-Disposition'] = f'attachment; filename="clientes-{timezone.localdate():%Y-%m-%d}.csv"'
    respuesta.write('﻿')  # para que Excel respete los acentos
    escritor = csv.writer(respuesta)
    escritor.writerow(['Nombre', 'Teléfono', 'Correo', 'Cómo te conoció', 'Eventos', 'Cotizaciones', 'Contratado',
                       'Pagado', 'Saldo', 'Próximo evento', 'Cliente desde', 'Notas'])
    for c in con_resumen(clientes_de(request.user), request.user).order_by('nombre'):
        escritor.writerow([
            c.nombre, c.telefono, c.email, c.get_origen_display() if c.origen else '', c.n_eventos, c.n_cotizaciones,
            f'{c.contratado:.2f}', f'{c.pagado:.2f}', f'{max(c.saldo, 0):.2f}',
            timezone.localtime(c.proximo).strftime('%Y-%m-%d') if c.proximo else '',
            timezone.localtime(c.creado).strftime('%Y-%m-%d'), c.notas.replace('\n', ' '),
        ])
    return respuesta
