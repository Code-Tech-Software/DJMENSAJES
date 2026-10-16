"""
Actualiza los tipos de contenido de los modelos reubicados para conservar el
historial del admin y los permisos ya asignados.
"""
from django.db import migrations

MOVIDOS = [
    ('eventos', 'usuario', 'cuentas', 'usuario'),
    ('eventos', 'sonidodj', 'colaboradores', 'colaborador'),
    ('eventos', 'banner', 'banners', 'banner'),
    ('eventos', 'mensaje', 'envivo', 'mensaje'),
]


def _mover(apps, schema_editor, pares):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    tipos = ContentType.objects.using(schema_editor.connection.alias)
    for origen_app, origen_modelo, destino_app, destino_modelo in pares:
        if tipos.filter(app_label=destino_app, model=destino_modelo).exists():
            continue
        tipos.filter(app_label=origen_app, model=origen_modelo).update(
            app_label=destino_app, model=destino_modelo,
        )


def adelante(apps, schema_editor):
    _mover(apps, schema_editor, MOVIDOS)


def atras(apps, schema_editor):
    _mover(apps, schema_editor, [(c, d, a, b) for a, b, c, d in MOVIDOS])


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('eventos', '0002_reubicar_modelos'),
        ('envivo', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(adelante, atras),
    ]
