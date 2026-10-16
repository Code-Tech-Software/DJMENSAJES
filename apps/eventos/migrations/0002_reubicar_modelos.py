"""
Apunta las relaciones de Evento a los modelos reubicados (cuentas, colaboradores,
banners) y retira esos modelos del estado de la app eventos. Mensaje pasa a la app
"envivo" (ver envivo/0001). No hay cambios en la base de datos.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0001_initial'),
        ('cuentas', '0001_initial'),
        ('colaboradores', '0001_initial'),
        ('banners', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='evento',
                    name='usuario',
                    field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='eventos', to='cuentas.usuario'),
                ),
                migrations.AlterField(
                    model_name='evento',
                    name='sonido_dj',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos', to='colaboradores.colaborador'),
                ),
                migrations.AlterField(
                    model_name='evento',
                    name='banner',
                    field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='eventos', to='banners.banner'),
                ),
                migrations.DeleteModel(name='Mensaje'),
                migrations.DeleteModel(name='Usuario'),
                migrations.DeleteModel(name='SonidoDJ'),
                migrations.DeleteModel(name='Banner'),
            ],
        ),
    ]
