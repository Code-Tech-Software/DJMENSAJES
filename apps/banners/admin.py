from django.contrib import admin
from django.utils.html import format_html

from .models import Banner


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'agencia', 'categoria', 'colaborador', 'estado', 'vista_previa')
    list_filter = ('agencia', 'categoria', 'estado', 'colaborador')
    search_fields = ('nombre', 'descripcion')

    @admin.display(description='Vista previa')
    def vista_previa(self, obj):
        imagen = obj.miniatura
        if imagen:
            return format_html('<img src="{}" style="height:40px;border-radius:6px">', imagen.url)
        return '—'
