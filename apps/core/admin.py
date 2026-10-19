from django.contrib import admin

from .models import Agencia, Ajustes


@admin.register(Agencia)
class AgenciaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'slug', 'activa', 'vence_el', 'creada')
    list_filter = ('activa',)
    search_fields = ('nombre', 'slug')
    prepopulated_fields = {'slug': ('nombre',)}


@admin.register(Ajustes)
class AjustesAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'agencia', 'whatsapp', 'actualizado')

    def has_add_permission(self, request):
        # Uno por agencia: se crea solo y se edita desde la página de Ajustes del panel
        return False

    def has_delete_permission(self, request, obj=None):
        return False
