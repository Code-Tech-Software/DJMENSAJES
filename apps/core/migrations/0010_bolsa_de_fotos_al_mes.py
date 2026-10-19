from django.db import migrations, models


class Migration(migrations.Migration):
    """El límite de fotos del plan pasa de "por evento" a una bolsa al mes que se reparte entre los eventos."""

    dependencies = [
        ('core', '0009_modulos_del_plan'),
    ]

    operations = [
        migrations.RenameField(
            model_name='plan',
            old_name='max_fotos_evento',
            new_name='max_fotos_mes',
        ),
        migrations.AlterField(
            model_name='plan',
            name='max_fotos_mes',
            field=models.PositiveIntegerField(blank=True, help_text='Fotos de invitados al mes para todos los eventos de la agencia; en cada evento se aparta una parte. Vacío = sin límite.', null=True, verbose_name='bolsa de fotos al mes'),
        ),
    ]
