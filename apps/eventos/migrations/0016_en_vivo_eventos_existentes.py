from django.db import migrations


def activar_en_existentes(apps, schema_editor):
    """Los eventos de antes ya tenían la experiencia en vivo (sus QR pueden estar impresos): se queda activa."""
    apps.get_model('eventos', 'Evento').objects.update(con_en_vivo=True)


class Migration(migrations.Migration):
    # Separada de la que agrega el campo: en PostgreSQL no se mezclan cambios de esquema y de datos

    dependencies = [
        ('eventos', '0015_extras_del_evento'),
    ]

    operations = [
        migrations.RunPython(activar_en_existentes, migrations.RunPython.noop),
    ]
