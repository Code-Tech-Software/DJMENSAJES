from django.contrib import admin

from .models import Invitacion, Invitado


@admin.register(Invitacion)
class InvitacionAdmin(admin.ModelAdmin):
    list_display = ('evento', 'plantilla', 'publicada', 'visitas', 'actualizado')
    list_filter = ('plantilla', 'publicada')
    search_fields = ('evento__nombre_evento', 'slug', 'nombres')
    readonly_fields = ('visitas',)


@admin.register(Invitado)
class InvitadoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'evento', 'pases', 'estado', 'pases_confirmados', 'mesa', 'vista_en', 'check_in_en')
    list_filter = ('estado', 'origen')
    search_fields = ('nombre', 'telefono', 'evento__nombre_evento')
    readonly_fields = ('token',)
