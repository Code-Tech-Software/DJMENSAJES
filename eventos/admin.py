from django.contrib import admin
from .models import Evento, Mensaje

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
