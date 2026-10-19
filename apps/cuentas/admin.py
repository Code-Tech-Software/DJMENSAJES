from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'agencia', 'rol', 'colaborador', 'is_active', 'last_login')
    list_filter = ('agencia', 'rol', 'colaborador', 'is_active', 'is_superuser')
    fieldsets = UserAdmin.fieldsets + (
        ('EventPro', {'fields': ('agencia', 'rol', 'colaborador', 'cargo', 'telefono', 'direccion', 'foto')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('EventPro', {'fields': ('first_name', 'last_name', 'agencia', 'rol', 'colaborador')}),
    )
