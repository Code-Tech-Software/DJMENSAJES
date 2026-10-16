"""
Reubica el modelo "SonidoDJ" de la app eventos como "Colaborador".
Solo cambia el estado: la tabla `eventos_sonidodj` se conserva.
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
                    name='Colaborador',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('nombre', models.CharField(max_length=200)),
                        ('eslogan', models.TextField(blank=True, null=True)),
                        ('facebook', models.URLField(blank=True, null=True)),
                        ('whatsapp', models.CharField(blank=True, max_length=50, null=True)),
                        ('instagram', models.URLField(blank=True, null=True)),
                        ('tiktok', models.URLField(blank=True, null=True)),
                        ('imagen1', models.ImageField(blank=True, null=True, upload_to='sonidos/')),
                        ('imagen2', models.ImageField(blank=True, null=True, upload_to='sonidos/')),
                        ('estado', models.BooleanField(default=True)),
                    ],
                    options={'db_table': 'eventos_sonidodj'},
                ),
            ],
        ),
    ]
