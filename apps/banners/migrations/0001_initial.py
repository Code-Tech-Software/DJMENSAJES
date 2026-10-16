"""
Reubica el modelo Banner desde la app eventos.
Solo cambia el estado: la tabla `eventos_banner` se conserva.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('eventos', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Banner',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('nombre', models.CharField(max_length=200)),
                        ('descripcion', models.TextField(blank=True, null=True)),
                        ('imagen1', models.ImageField(blank=True, null=True, upload_to='banners/')),
                        ('imagen2', models.ImageField(blank=True, null=True, upload_to='banners/')),
                        ('imagen3', models.ImageField(blank=True, null=True, upload_to='banners/')),
                        ('estado', models.BooleanField(default=True)),
                    ],
                    options={'db_table': 'eventos_banner'},
                ),
            ],
        ),
    ]
