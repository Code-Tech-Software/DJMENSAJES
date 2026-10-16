from django.db import migrations, models

import apps.eventos.models


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0006_generar_codigos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='evento',
            name='codigo',
            field=models.CharField(default=apps.eventos.models._codigo_unico, editable=False, max_length=12, unique=True),
        ),
        migrations.AlterField(
            model_name='evento',
            name='token_dj',
            field=models.CharField(default=apps.eventos.models._token_dj, editable=False, max_length=40, unique=True),
        ),
    ]
