"""
Convierte los campos de texto "padres" y "padrinos" en menciones editables y crea
el primer lugar de cada invitación a partir del lugar registrado en el evento.
"""
from django.db import migrations


def adelante(apps, schema_editor):
    Invitacion = apps.get_model('invitaciones', 'Invitacion')
    Mencion = apps.get_model('invitaciones', 'Mencion')
    Ubicacion = apps.get_model('invitaciones', 'Ubicacion')
    db = schema_editor.connection.alias
    for invitacion in Invitacion.objects.using(db).select_related('evento'):
        orden = 0
        for titulo, texto in [('Con la bendición de nuestros padres', invitacion.padres),
                              ('Padrinos', invitacion.padrinos)]:
            if texto and texto.strip():
                Mencion.objects.using(db).create(invitacion=invitacion, titulo=titulo, nombres=texto.strip(), orden=orden)
                orden += 1
        evento = invitacion.evento
        if evento.lugar and not Ubicacion.objects.using(db).filter(invitacion=invitacion).exists():
            Ubicacion.objects.using(db).create(
                invitacion=invitacion, tipo='recepcion', lugar=evento.lugar[:150],
                direccion=evento.direccion or '', url_mapa=evento.url_mapa or '',
            )


class Migration(migrations.Migration):

    dependencies = [
        ('invitaciones', '0002_lugares_personas_galeria'),
        ('eventos', '0007_codigos_unicos'),
    ]

    operations = [
        migrations.RunPython(adelante, migrations.RunPython.noop),
    ]
