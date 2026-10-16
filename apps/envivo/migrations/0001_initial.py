"""
Reubica el modelo Mensaje desde la app eventos.
Solo cambia el estado: la tabla `eventos_mensaje` se conserva.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('eventos', '0002_reubicar_modelos'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Mensaje',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('nombre', models.CharField(max_length=100)),
                        ('tipo', models.CharField(choices=[('saludo', 'Saludo'), ('cancion', 'Canción')], max_length=50)),
                        ('mensaje', models.TextField()),
                        ('vip', models.BooleanField(default=False)),
                        ('estado', models.BooleanField(default=True)),
                        ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                        ('evento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mensajes', to='eventos.evento')),
                    ],
                    options={'db_table': 'eventos_mensaje'},
                ),
            ],
        ),
    ]
