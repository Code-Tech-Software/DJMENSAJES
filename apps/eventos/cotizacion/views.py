"""Panel de cotizaciones de la agencia: lista, catálogo, cotizador, detalle, PDF y acciones."""
import json
import re
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from apps.core.marca import Marca
from apps.core.mixins import AsignarAgenciaMixin, DeLaAgenciaMixin, FormularioModalMixin, respuesta_error, respuesta_ok

from ..asistente import sugerencias
from ..models import CategoriaServicio, Cotizacion, Paquete, Servicio, orden_servicio
from .forms import CotizacionForm, PaqueteForm, ServicioForm, datos_catalogo
from .pdf import generar_pdf, nombre_archivo
from .servicios import (aceptar, cargar_catalogo_ejemplo, convertir_en_evento, duplicar, guardar_conceptos, nueva_para,
                        url_whatsapp)

E = Cotizacion.Estado


def cotizaciones_de(usuario):
    return Cotizacion.objects.visibles_para(usuario)


def obtener(request, pk):
    return get_object_or_404(cotizaciones_de(request.user).select_related('agencia__plan', 'colaborador', 'evento'), pk=pk)


def _url_publica(request, cotizacion):
    return request.build_absolute_uri(cotizacion.url_cliente())


# --- Lista ------------------------------------------------------------------------------------------

FILTROS = (
    ('', 'Todas', 'ph ph-files'),
    ('borrador', 'Borradores', 'ph ph-note-pencil'),
    ('enviada', 'Enviadas', 'ph ph-paper-plane-tilt'),
    ('aceptada', 'Aceptadas', 'ph ph-seal-check'),
    ('rechazada', 'Rechazadas', 'ph ph-x-circle'),
    ('vencida', 'Vencidas', 'ph ph-hourglass-low'),
)


def _filtro(estado, hoy):
    abiertas = Q(estado__in=[E.BORRADOR, E.ENVIADA])
    return {
        'borrador': Q(estado=E.BORRADOR, vigencia__gte=hoy),
        'enviada': Q(estado=E.ENVIADA, vigencia__gte=hoy),
        'aceptada': Q(estado=E.ACEPTADA),
        'rechazada': Q(estado=E.RECHAZADA),
        'vencida': abiertas & Q(vigencia__lt=hoy),
    }.get(estado, Q())


@login_required
def lista(request):
    hoy = timezone.localdate()
    base = cotizaciones_de(request.user)
    estado = request.GET.get('estado', '')
    q = request.GET.get('q', '').strip()
    conteos = base.aggregate(todas=Count('pk'), **{clave: Count('pk', filter=_filtro(clave, hoy)) for clave, *_ in FILTROS if clave})
    cotizaciones = base.filter(_filtro(estado, hoy)).select_related('evento', 'colaborador').prefetch_related('conceptos')
    if q:
        filtro = Q(cliente_nombre__icontains=q) | Q(nombre_evento__icontains=q) | Q(lugar__icontains=q)
        numero = re.sub(r'\D', '', q)
        if numero:
            filtro |= Q(numero=int(numero))
        cotizaciones = cotizaciones.filter(filtro)
    pagina = Paginator(cotizaciones, 30).get_page(request.GET.get('page'))
    query = urlencode({k: v for k, v in (('estado', estado), ('q', q)) if v})

    # Números del mes: lo cotizado, lo aceptado y la tasa de cierre de los últimos 90 días
    inicio_mes = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    del_mes = list(base.filter(creado__gte=inicio_mes).prefetch_related('conceptos'))
    aceptadas_mes = list(base.filter(estado=E.ACEPTADA, respondida_el__gte=inicio_mes).prefetch_related('conceptos'))
    cerradas = base.filter(creado__gte=timezone.now() - timedelta(days=90), estado__in=[E.ACEPTADA, E.RECHAZADA])
    n_cerradas = cerradas.count()
    stats = {
        'cotizado': sum(c.total for c in del_mes), 'n_mes': len(del_mes),
        'aceptado': sum(c.total for c in aceptadas_mes), 'n_aceptadas': len(aceptadas_mes),
        'por_responder': conteos['enviada'],
        'tasa': round(cerradas.filter(estado=E.ACEPTADA).count() * 100 / n_cerradas) if n_cerradas else None,
    }
    return render(request, 'cotizaciones/lista.html', {
        'pagina': pagina, 'query': query, 'cotizaciones': pagina.object_list, 'estado': estado, 'q': q, 'stats': stats,
        'filtros': [(clave, nombre, icono, conteos[clave or 'todas']) for clave, nombre, icono in FILTROS],
        'catalogo_vacio': not Servicio.objects.filter(agencia_id=request.user.agencia_id).exists(),
    })


# --- Catálogo -----------------------------------------------------------------------------------------

def _puede_editar_catalogo(usuario):
    return usuario.is_authenticated and usuario.agencia_id and usuario.ve_todo


@login_required
def catalogo(request):
    agencia_id = request.user.agencia_id
    nombres = dict(CategoriaServicio.choices)
    servicios = Servicio.objects.filter(agencia_id=agencia_id).annotate(n_paquetes=Count('paquetes'))
    grupos = {}
    for s in sorted(servicios, key=lambda s: (orden_servicio(s), s.orden, s.nombre.lower())):
        grupos.setdefault(s.categoria, {'nombre': nombres[s.categoria], 'icono': s.icono, 'servicios': []})['servicios'].append(s)
    return render(request, 'cotizaciones/catalogo.html', {
        'grupos': list(grupos.values()), 'n_servicios': len(servicios),
        'paquetes': Paquete.objects.filter(agencia_id=agencia_id).prefetch_related('items__servicio'),
        'puede_editar': _puede_editar_catalogo(request.user),
    })


class CatalogoMixin(LoginRequiredMixin, FormularioModalMixin):
    """Solo administradores y coordinadores arman el catálogo; el resto lo usa al cotizar.
    (Va después de AsignarAgenciaMixin para que la agencia se asigne antes de guardar.)"""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not _puede_editar_catalogo(request.user):
            raise PermissionDenied('Solo administradores y coordinadores editan el catálogo.')
        return super().dispatch(request, *args, **kwargs)


class ServicioCrear(AsignarAgenciaMixin, CatalogoMixin, CreateView):
    model = Servicio
    form_class = ServicioForm
    template_modal = 'cotizaciones/form_servicio.html'
    titulo = 'Nuevo servicio'
    subtitulo = 'Lo que cobras: aparecerá al armar cotizaciones.'
    icono = 'ph ph-tag'
    texto_boton = 'Agregar al catálogo'
    mensaje_exito = 'Servicio agregado al catálogo.'


class ServicioEditar(DeLaAgenciaMixin, CatalogoMixin, UpdateView):
    model = Servicio
    form_class = ServicioForm
    template_modal = 'cotizaciones/form_servicio.html'
    titulo = 'Editar servicio'
    icono = 'ph ph-tag'
    mensaje_exito = 'Servicio actualizado. Las cotizaciones ya hechas conservan su precio.'

    def get_subtitulo(self):
        return self.object.nombre


class PaqueteCrear(AsignarAgenciaMixin, CatalogoMixin, CreateView):
    model = Paquete
    form_class = PaqueteForm
    template_modal = 'cotizaciones/form_paquete.html'
    titulo = 'Nuevo paquete'
    subtitulo = 'Junta servicios con un precio especial.'
    icono = 'ph ph-package'
    tamano = 'lg'
    texto_boton = 'Crear paquete'
    mensaje_exito = 'Paquete creado.'


class PaqueteEditar(DeLaAgenciaMixin, CatalogoMixin, UpdateView):
    model = Paquete
    form_class = PaqueteForm
    template_modal = 'cotizaciones/form_paquete.html'
    titulo = 'Editar paquete'
    icono = 'ph ph-package'
    tamano = 'lg'
    mensaje_exito = 'Paquete actualizado.'

    def get_subtitulo(self):
        return self.object.nombre


def _solo_catalogo(request):
    if not _puede_editar_catalogo(request.user):
        raise PermissionDenied('Solo administradores y coordinadores editan el catálogo.')


@login_required
@require_POST
def servicio_eliminar(request, pk):
    _solo_catalogo(request)
    servicio = get_object_or_404(Servicio, pk=pk, agencia_id=request.user.agencia_id)
    nombre = servicio.nombre
    servicio.delete()
    return respuesta_ok(request, f'Se quitó "{nombre}" del catálogo.')


@login_required
@require_POST
def paquete_eliminar(request, pk):
    _solo_catalogo(request)
    paquete = get_object_or_404(Paquete, pk=pk, agencia_id=request.user.agencia_id)
    nombre = paquete.nombre
    paquete.delete()
    return respuesta_ok(request, f'Se eliminó el paquete "{nombre}".')


@login_required
@require_POST
def catalogo_ejemplo(request):
    _solo_catalogo(request)
    creados = cargar_catalogo_ejemplo(request.user.agencia)
    return respuesta_ok(request, f'Listo: {creados} servicios y sus paquetes de ejemplo. Ajusta los precios a los tuyos.'
                        if creados else 'Tu catálogo ya tenía esos servicios.')


# --- Cotizador ------------------------------------------------------------------------------------------

@login_required
def editar(request, pk=None):
    """Arma o edita una cotización: datos del cliente y del evento, conceptos del catálogo y condiciones."""
    if not request.user.agencia_id:
        raise PermissionDenied('Tu cuenta no pertenece a ninguna agencia.')
    cotizacion = obtener(request, pk) if pk else None
    if cotizacion and cotizacion.estado == E.ACEPTADA:
        messages.info(request, 'Esta cotización ya fue aceptada: los cambios se hacen en su evento.')
        return redirect(cotizacion.get_absolute_url())
    instancia = cotizacion or Cotizacion(agencia_id=request.user.agencia_id, creado_por=request.user)
    form = CotizacionForm(request.POST or None, instance=instancia, usuario=request.user,
                          initial=None if cotizacion else nueva_para(request.user))
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            obj = form.save(commit=False)
            if not request.user.ve_todo and request.user.colaborador_id:
                obj.colaborador_id = request.user.colaborador_id
            obj.save()
            guardar_conceptos(obj, form.cleaned_data['conceptos'])
        messages.success(request, f'Cotización {obj.folio} guardada.' if cotizacion else f'¡Lista! Cotización {obj.folio} creada.')
        destino = obj.get_absolute_url()
        if request.POST.get('despues') == 'pdf':
            destino += '?pdf=1'
        return redirect(destino)
    return render(request, 'cotizaciones/editor.html', {
        'form': form, 'cotizacion': cotizacion,
        'catalogo': json.dumps(datos_catalogo(request.user.agencia_id)),
        'sugerencias': json.dumps(sugerencias(request.user)),
        'puede_editar_catalogo': _puede_editar_catalogo(request.user),
    })


# --- Detalle y acciones -------------------------------------------------------------------------------

@login_required
def detalle(request, pk):
    cotizacion = obtener(request, pk)
    return render(request, 'cotizaciones/detalle.html', {
        'cotizacion': cotizacion, 'marca': Marca(cotizacion), 'url_publica': _url_publica(request, cotizacion),
        'abrir_pdf': request.GET.get('pdf') == '1',
    })


def respuesta_pdf(cotizacion, request, descargar=False):
    contenido = generar_pdf(cotizacion, Marca(cotizacion), _url_publica(request, cotizacion))
    respuesta = HttpResponse(contenido, content_type='application/pdf')
    disposicion = 'attachment' if descargar else 'inline'
    respuesta['Content-Disposition'] = f'{disposicion}; filename="{nombre_archivo(cotizacion)}"'
    return respuesta


@login_required
def pdf(request, pk):
    return respuesta_pdf(obtener(request, pk), request, descargar=request.GET.get('descargar') == '1')


@login_required
def whatsapp(request, pk):
    """Abre WhatsApp con el mensaje y el enlace para el cliente; la cotización queda como enviada."""
    cotizacion = obtener(request, pk)
    if cotizacion.estado == E.BORRADOR:
        cotizacion.estado = E.ENVIADA
        cotizacion.enviada_el = timezone.now()
        cotizacion.save(update_fields=['estado', 'enviada_el', 'actualizado'])
    return redirect(url_whatsapp(cotizacion, _url_publica(request, cotizacion), Marca(cotizacion).nombre))


@login_required
@require_POST
def marcar_enviada(request, pk):
    cotizacion = obtener(request, pk)
    if cotizacion.estado == E.BORRADOR:
        cotizacion.estado = E.ENVIADA
        cotizacion.enviada_el = timezone.now()
        cotizacion.save(update_fields=['estado', 'enviada_el', 'actualizado'])
    return respuesta_ok(request, 'Marcada como enviada.')


@login_required
@require_POST
def aceptar_cotizacion(request, pk):
    """El cliente aceptó (por teléfono, en persona…): se marca aceptada y se crea el evento."""
    cotizacion = obtener(request, pk)
    if cotizacion.estado == E.ACEPTADA:
        return respuesta_error(request, 'Esta cotización ya estaba aceptada.')
    evento, motivo = aceptar(cotizacion, request.user)
    if evento is None:
        return respuesta_ok(request, f'Cotización aceptada, pero no se pudo crear el evento: {motivo}')
    return respuesta_ok(request, f'¡Aceptada! Se creó el evento "{evento.nombre_evento}" con sus servicios y precio.',
                        redirect=evento.get_absolute_url())


@login_required
@require_POST
def crear_evento(request, pk):
    """Para una cotización aceptada que aún no tiene evento (p. ej. el plan estaba lleno)."""
    cotizacion = obtener(request, pk)
    if cotizacion.estado != E.ACEPTADA:
        return respuesta_error(request, 'Primero marca la cotización como aceptada.')
    evento, motivo = convertir_en_evento(cotizacion, request.user)
    if evento is None:
        return respuesta_error(request, motivo, status=403)
    return respuesta_ok(request, f'Se creó el evento "{evento.nombre_evento}".', redirect=evento.get_absolute_url())


@login_required
@require_POST
def rechazar(request, pk):
    cotizacion = obtener(request, pk)
    if cotizacion.estado == E.ACEPTADA:
        return respuesta_error(request, 'Ya fue aceptada; si se cancela, cambia la etapa de su evento.')
    cotizacion.estado = E.RECHAZADA
    cotizacion.respondida_el = timezone.now()
    cotizacion.save(update_fields=['estado', 'respondida_el', 'actualizado'])
    return respuesta_ok(request, 'Marcada como rechazada.')


@login_required
@require_POST
def duplicar_cotizacion(request, pk):
    copia = duplicar(obtener(request, pk), request.user)
    messages.success(request, f'Se creó {copia.folio} como copia. Ajusta lo que necesites.')
    return respuesta_ok(request, redirect=reverse('cotizaciones:editar', args=[copia.pk]))


@login_required
@require_POST
def eliminar(request, pk):
    cotizacion = obtener(request, pk)
    folio = cotizacion.folio
    cotizacion.delete()
    return respuesta_ok(request, f'Se eliminó la cotización {folio}.', redirect=reverse('cotizaciones:lista'))
