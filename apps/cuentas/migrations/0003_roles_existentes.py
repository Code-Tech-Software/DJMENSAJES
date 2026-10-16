"""
Antes de existir los roles, cualquier usuario podía administrar todo el panel.
Para no quitar accesos, los usuarios existentes quedan como administradores.
"""
from django.db import migrations


def asignar(apps, schema_editor):
    Usuario = apps.get_model('cuentas', 'Usuario')
    Usuario.objects.using(schema_editor.connection.alias).update(rol='admin')


class Migration(migrations.Migration):

    dependencies = [
        ('cuentas', '0002_roles_y_colaborador'),
    ]

    operations = [
        migrations.RunPython(asignar, migrations.RunPython.noop),
    ]
