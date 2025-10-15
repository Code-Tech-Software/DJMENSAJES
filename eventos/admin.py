from django.contrib import admin
from .models import Evento, Mensaje, Banner, SonidoDJ

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('nombre_evento', 'usuario', 'tipo_evento', 'fecha_inicio_evento', 'estado')
    list_filter = ('tipo_evento', 'estado')
    search_fields = ('nombre_evento', 'usuario__username')

@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'vip', 'evento', 'estado')
    list_filter = ('vip', 'tipo', 'estado')
    search_fields = ('nombre', 'mensaje')

# 🖼️ Mostrar imagen en el admin
from django.utils.html import format_html


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion_corta', 'estado', 'preview_imagen1')
    list_filter = ('estado',)
    search_fields = ('nombre', 'descripcion')
    readonly_fields = ('preview_imagen1', 'preview_imagen2', 'preview_imagen3')

    def descripcion_corta(self, obj):
        return (obj.descripcion[:60] + '...') if obj.descripcion else ''
    descripcion_corta.short_description = "Descripción"

    def preview_imagen1(self, obj):
        if obj.imagen1:
            return format_html('<img src="{}" width="100" style="border-radius:8px;">', obj.imagen1.url)
        return "Sin imagen"
    preview_imagen1.short_description = "Imagen 1"

    def preview_imagen2(self, obj):
        if obj.imagen2:
            return format_html('<img src="{}" width="100" style="border-radius:8px;">', obj.imagen2.url)
        return "Sin imagen"
    preview_imagen2.short_description = "Imagen 2"

    def preview_imagen3(self, obj):
        if obj.imagen3:
            return format_html('<img src="{}" width="100" style="border-radius:8px;">', obj.imagen3.url)
        return "Sin imagen"
    preview_imagen3.short_description = "Imagen 3"


@admin.register(SonidoDJ)
class SonidoDJAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'eslogan_corto', 'facebook', 'instagram', 'estado', 'preview_imagen1')
    list_filter = ('estado',)
    search_fields = ('nombre', 'eslogan', 'facebook', 'instagram', 'tiktok', 'whatsapp')
    readonly_fields = ('preview_imagen1', 'preview_imagen2')

    def eslogan_corto(self, obj):
        return (obj.eslogan[:60] + '...') if obj.eslogan else ''
    eslogan_corto.short_description = "Eslogan"

    def preview_imagen1(self, obj):
        if obj.imagen1:
            return format_html('<img src="{}" width="100" style="border-radius:8px;">', obj.imagen1.url)
        return "Sin imagen"
    preview_imagen1.short_description = "Imagen 1"

    def preview_imagen2(self, obj):
        if obj.imagen2:
            return format_html('<img src="{}" width="100" style="border-radius:8px;">', obj.imagen2.url)
        return "Sin imagen"
    preview_imagen2.short_description = "Imagen 2"