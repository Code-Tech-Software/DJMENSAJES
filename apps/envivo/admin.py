from django.contrib import admin

from .models import Mensaje


@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'mensaje', 'vip', 'estatus', 'en_pantalla', 'evento', 'fecha_creacion')
    list_filter = ('tipo', 'vip', 'estatus', 'en_pantalla')
    search_fields = ('nombre', 'mensaje', 'artista', 'evento__nombre_evento')
    date_hierarchy = 'fecha_creacion'
