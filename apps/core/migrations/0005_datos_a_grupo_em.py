"""
EventPro pasa a ser multi-agencia: lo que ya existía (equipo, sub-agencias, banners, eventos y ajustes)
pertenecía a un solo negocio y queda en la agencia "Grupo EM". En una base nueva no hace nada.

Va en su propia migración (separada de los AddField y de los AlterField que vuelven obligatorio el campo)
para que PostgreSQL no falle con "pending trigger events" al mezclar cambios de datos y de tablas.
"""
from django.core.cache import cache
from django.db import migrations


def a_grupo_em(apps, schema_editor):
    Agencia = apps.get_model('core', 'Agencia')
    Ajustes = apps.get_model('core', 'Ajustes')
    modelos = [apps.get_model(*m) for m in (('cuentas', 'Usuario'), ('colaboradores', 'Colaborador'),
                                              ('banners', 'Banner'), ('eventos', 'Evento'))]
    if not any(m.objects.exists() for m in modelos) and not Ajustes.objects.exists():
        return

    agencia, _ = Agencia.objects.get_or_create(slug='grupo-em', defaults={'nombre': 'Grupo EM'})
    for modelo in modelos:
        modelo.objects.filter(agencia__isnull=True).update(agencia=agencia)

    ajustes = Ajustes.objects.filter(agencia__isnull=True).order_by('pk').first()
    if ajustes and not Ajustes.objects.filter(agencia=agencia).exists():
        ajustes.agencia = agencia
        if ajustes.nombre in ('', 'EventPro'):  # el nombre de fábrica: la agencia es Grupo EM
            ajustes.nombre = 'Grupo EM'
        ajustes.save(update_fields=['agencia', 'nombre'])

    try:  # los ajustes se guardan en caché por agencia
        cache.delete_many(['core:ajustes', f'core:ajustes:{agencia.pk}'])
    except Exception:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_agencias'),
        ('cuentas', '0004_usuario_agencia'),
        ('colaboradores', '0004_colaborador_agencia'),
        ('banners', '0004_banner_agencia'),
        ('eventos', '0010_evento_agencia'),
    ]

    operations = [
        migrations.RunPython(a_grupo_em, migrations.RunPython.noop),
    ]
