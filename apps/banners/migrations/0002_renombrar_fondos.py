from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('banners', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(model_name='banner', old_name='imagen1', new_name='fondo_movil'),
        migrations.RenameField(model_name='banner', old_name='imagen2', new_name='fondo_pantalla'),
        migrations.RenameField(model_name='banner', old_name='imagen3', new_name='portada'),
    ]
