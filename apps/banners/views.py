from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from apps.core.mixins import AsignarAgenciaMixin, DeLaAgenciaMixin, FormularioModalMixin, respuesta_ok
from apps.cuentas.permisos import CatalogosRequeridoMixin, catalogos_requerido

from .forms import BannerForm
from .models import Banner


@catalogos_requerido
def lista(request):
    categoria = request.GET.get('categoria', '')
    q = request.GET.get('q', '').strip()
    banners = (Banner.objects.disponibles_para(request.user.agencia_id).select_related('colaborador')
               .annotate(n_eventos=Count('eventos', filter=Q(eventos__agencia_id=request.user.agencia_id))))
    if categoria:
        banners = banners.filter(categoria=categoria)
    if q:
        banners = banners.filter(Q(nombre__icontains=q) | Q(descripcion__icontains=q))
    return render(request, 'banners/lista.html', {
        'banners': banners, 'categoria': categoria, 'q': q,
        'categorias': Banner.Categoria.choices,
    })


class BannerCrear(AsignarAgenciaMixin, CatalogosRequeridoMixin, FormularioModalMixin, CreateView):
    model = Banner
    form_class = BannerForm
    template_modal = 'banners/partials/form.html'
    titulo = 'Nuevo banner'
    subtitulo = 'Un juego de fondos para pantallas e invitaciones.'
    icono = 'ph ph-image'
    tamano = 'lg'
    texto_boton = 'Guardar banner'
    mensaje_exito = 'Banner creado.'


class BannerEditar(DeLaAgenciaMixin, CatalogosRequeridoMixin, FormularioModalMixin, UpdateView):
    model = Banner
    form_class = BannerForm
    template_modal = 'banners/partials/form.html'
    titulo = 'Editar banner'
    icono = 'ph ph-image'
    tamano = 'lg'
    mensaje_exito = 'Banner actualizado.'

    def get_subtitulo(self):
        return self.object.nombre


@catalogos_requerido
@require_POST
def eliminar(request, pk):
    banner = get_object_or_404(Banner, pk=pk, agencia_id=request.user.agencia_id)
    banner.delete()
    return respuesta_ok(request, 'Banner eliminado.')
