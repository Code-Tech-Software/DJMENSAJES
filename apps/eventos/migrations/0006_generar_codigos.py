"""Genera el código público y el token del panel DJ de los eventos existentes."""
from django.db import migrations

from apps.core.utils import generar_codigo, generar_token


def generar(apps, schema_editor):
    Evento = apps.get_model('eventos', 'Evento')
    eventos = Evento.objects.using(schema_editor.connection.alias)
    usados = set(eventos.exclude(codigo=None).values_list('codigo', flat=True))
    for evento in eventos.filter(codigo=None) | eventos.filter(token_dj=None):
        if not evento.codigo:
            codigo = generar_codigo(7)
            while codigo in usados:
                codigo = generar_codigo(7)
            usados.add(codigo)
            evento.codigo = codigo
        if not evento.token_dj:
            evento.token_dj = generar_token(18)
        evento.save(update_fields=['codigo', 'token_dj'])


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0005_datos_de_negocio'),
    ]

    operations = [
        migrations.RunPython(generar, migrations.RunPython.noop),
    ]
