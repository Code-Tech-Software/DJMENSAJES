from django.contrib import admin
from django.utils.html import format_html

from .models import Colaborador


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'ciudad', 'responsable', 'telefono', 'estado', 'vista_logo')
    list_filter = ('tipo', 'estado')
    search_fields = ('nombre', 'ciudad', 'responsable', 'email')

    @admin.display(description='Logo')
    def vista_logo(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="height:32px;border-radius:6px;background:#0f172a;padding:2px">', obj.logo.url)
        return '—'
