"""Arma el directorio de clientes con los eventos y cotizaciones que ya existían (separado del cambio de esquema)."""
from django.db import migrations


def _telefono(telefono):
    digitos = ''.join(c for c in telefono or '' if c.isdigit())
    return digitos[-10:] if len(digitos) > 10 else digitos


def armar_directorio(apps, schema_editor):
    Cliente = apps.get_model('eventos', 'Cliente')
    Evento = apps.get_model('eventos', 'Evento')
    Cotizacion = apps.get_model('eventos', 'Cotizacion')
    por_agencia = {}  # agencia -> {'tel': {}, 'email': {}, 'nombre': {}}

    def cliente_para(obj):
        nombre = ' '.join((obj.cliente_nombre or '').split())
        if not nombre:
            return None
        indice = por_agencia.get(obj.agencia_id)
        if indice is None:  # los clientes que la agencia ya tenga en el directorio
            indice = por_agencia[obj.agencia_id] = {'tel': {}, 'email': {}, 'nombre': {}}
            for c in Cliente.objects.filter(agencia_id=obj.agencia_id).order_by('pk'):
                if len(c.telefono_normalizado) >= 7:
                    indice['tel'].setdefault(c.telefono_normalizado, c)
                if c.email:
                    indice['email'].setdefault(c.email.lower(), c)
                indice['nombre'].setdefault(' '.join(c.nombre.split()).lower(), c)
        tel, email = _telefono(obj.cliente_telefono), (obj.cliente_email or '').strip().lower()
        cliente = (len(tel) >= 7 and indice['tel'].get(tel)) or (email and indice['email'].get(email)) or None
        if cliente is None:
            mismo = indice['nombre'].get(nombre.lower())
            if mismo and not (tel and mismo.telefono_normalizado and mismo.telefono_normalizado != tel) \
                    and not (email and mismo.email and mismo.email != email):
                cliente = mismo
        if cliente is None:
            cliente = Cliente.objects.create(agencia_id=obj.agencia_id, nombre=nombre[:150], telefono=obj.cliente_telefono or '',
                                             email=email, telefono_normalizado=tel, creado_por_id=obj.creado_por_id, creado=obj.creado)
        else:
            cambios = []
            if tel and not cliente.telefono:
                cliente.telefono, cliente.telefono_normalizado = obj.cliente_telefono, tel
                cambios += ['telefono', 'telefono_normalizado']
            if email and not cliente.email:
                cliente.email = email
                cambios.append('email')
            if cambios:
                cliente.save(update_fields=cambios)
        if len(tel) >= 7:
            indice['tel'].setdefault(tel, cliente)
        if email:
            indice['email'].setdefault(email, cliente)
        indice['nombre'].setdefault(nombre.lower(), cliente)
        return cliente

    for modelo in (Evento, Cotizacion):
        for obj in modelo.objects.filter(cliente__isnull=True).exclude(cliente_nombre='').order_by('creado', 'pk'):
            cliente = cliente_para(obj)
            if cliente is not None:
                modelo.objects.filter(pk=obj.pk).update(cliente=cliente)


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0017_clientes'),
    ]

    operations = [
        migrations.RunPython(armar_directorio, migrations.RunPython.noop),
    ]
