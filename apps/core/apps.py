from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Núcleo'

    def ready(self):
        from . import senales  # noqa: F401  (bitácora automática)
