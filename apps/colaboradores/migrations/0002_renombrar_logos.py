from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('colaboradores', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(model_name='colaborador', old_name='imagen1', new_name='logo_principal'),
        migrations.RenameField(model_name='colaborador', old_name='imagen2', new_name='logo_secundario'),
    ]
