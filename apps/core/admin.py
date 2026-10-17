from django.contrib import admin

from .models import Ajustes


@admin.register(Ajustes)
class AjustesAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'whatsapp', 'actualizado')

    def has_add_permission(self, request):
        # Es un solo registro: se edita desde la página de Ajustes del panel
        return not Ajustes.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
