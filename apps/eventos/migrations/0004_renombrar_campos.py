from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0003_tipos_contenido'),
    ]

    operations = [
        migrations.RenameField(model_name='evento', old_name='usuario', new_name='creado_por'),
        migrations.RenameField(model_name='evento', old_name='sonido_dj', new_name='colaborador'),
    ]
