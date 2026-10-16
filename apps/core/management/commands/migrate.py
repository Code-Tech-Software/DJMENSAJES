"""
`migrate` con un paso previo para bases de datos creadas antes de reorganizar
el proyecto en apps.

El modelo de usuario se movió de la app "eventos" a "cuentas" conservando su
tabla. Django exige que la primera migración de la app del usuario esté aplicada
antes que `admin.0001_initial`; como en una base existente el admin ya está
migrado, registramos `cuentas.0001_initial` (que solo cambia el estado y no toca
tablas) como aplicada. En una base nueva este paso no hace nada.
"""
from django.core.management.commands.migrate import Command as MigrateCommand
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder

MIGRACIONES_DE_ESTADO = [
    # (requiere aplicada, se registra como aplicada)
    (('eventos', '0001_initial'), ('cuentas', '0001_initial')),
]


def preparar_historial(conexion, stdout=None):
    registro = MigrationRecorder(conexion)
    if not registro.has_table():
        return
    aplicadas = registro.applied_migrations()
    for requisito, migracion in MIGRACIONES_DE_ESTADO:
        if requisito in aplicadas and migracion not in aplicadas:
            registro.record_applied(*migracion)
            if stdout:
                stdout.write(f'  Historial preparado: {migracion[0]}.{migracion[1]} registrada.')


class Command(MigrateCommand):
    def handle(self, *args, **options):
        preparar_historial(connections[options['database']], self.stdout)
        return super().handle(*args, **options)
