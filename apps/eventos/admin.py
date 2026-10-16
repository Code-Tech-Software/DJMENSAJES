from django.contrib import admin

from .models import ActividadItinerario, Evento, Pago


class ActividadInline(admin.TabularInline):
    model = ActividadItinerario
    extra = 0


class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('nombre_evento', 'tipo_evento', 'etapa', 'fecha_inicio_evento', 'colaborador', 'estado', 'codigo')
    list_filter = ('tipo_evento', 'etapa', 'estado', 'colaborador')
    search_fields = ('nombre_evento', 'lugar', 'cliente_nombre', 'codigo')
    date_hierarchy = 'fecha_inicio_evento'
    readonly_fields = ('codigo', 'token_dj', 'creado', 'actualizado')
    inlines = [ActividadInline, PagoInline]
