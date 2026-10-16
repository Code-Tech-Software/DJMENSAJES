"""Etiquetas y filtros de la interfaz Grupo EM."""
from decimal import Decimal, InvalidOperation

from django import forms, template
from django.utils import timezone
from django.utils.html import format_html

from apps.core.utils import iniciales as _iniciales
from apps.eventos.models import ICONOS_TIPO

register = template.Library()


@register.inclusion_tag('components/campo.html')
def campo(field, icono='', clase='', tipo=None, placeholder=None, oscuro=False, opcional=False):
    """Renderiza un campo con etiqueta, ayuda, errores y el control adecuado."""
    widget = field.field.widget
    if tipo is None:
        if isinstance(widget, forms.CheckboxInput):
            tipo = 'switch'
        elif isinstance(widget, forms.FileInput):
            tipo = 'archivo'
        else:
            tipo = 'input'
    if placeholder:
        widget.attrs['placeholder'] = placeholder

    archivo_url = ''
    if tipo == 'archivo':
        valor = field.value()
        if valor and hasattr(valor, 'url'):
            try:
                archivo_url = valor.url
            except Exception:  # almacenamiento no disponible
                archivo_url = ''
    return {
        'field': field,
        'icono': icono,
        'clase': clase,
        'tipo': tipo,
        'oscuro': oscuro,
        'opcional': opcional or (not field.field.required and tipo == 'input'),
        'archivo_url': archivo_url,
    }


@register.filter
def icono_tipo(tipo):
    return ICONOS_TIPO.get(tipo, ICONOS_TIPO['otro'])


@register.filter
def iniciales(texto):
    return _iniciales(str(texto))


@register.filter
def monograma(texto):
    """'Ana & Luis' -> 'A&L'; 'Sofía' -> 'S'."""
    import re
    partes = [p.strip() for p in re.split(r'\s+(?:&|y|e)\s+|\s*&\s*', str(texto or '')) if p.strip()]
    if len(partes) >= 2:
        return f'{partes[0][0]}&{partes[1][0]}'.upper()
    return _iniciales(str(texto), maximo=1)


@register.filter
def moneda(valor):
    try:
        numero = Decimal(valor or 0)
    except (InvalidOperation, TypeError):
        return valor
    entero = f'{numero:,.2f}'
    if entero.endswith('.00'):
        entero = entero[:-3]
    return f'${entero}'


@register.filter
def porcentaje(parte, total):
    try:
        total = float(total or 0)
        return 0 if not total else min(100, round(float(parte or 0) * 100 / total))
    except (TypeError, ValueError):
        return 0


@register.filter
def hace(fecha):
    """'hace 5 min', 'hace 2 h', 'ayer'…"""
    if not fecha:
        return ''
    delta = timezone.now() - fecha
    segundos = int(delta.total_seconds())
    if segundos < 0:
        return 'en el futuro'
    if segundos < 60:
        return 'justo ahora'
    if segundos < 3600:
        return f'hace {segundos // 60} min'
    if segundos < 86400:
        return f'hace {segundos // 3600} h'
    if segundos < 172800:
        return 'ayer'
    if segundos < 604800:
        return f'hace {segundos // 86400} días'
    return timezone.localtime(fecha).strftime('%d/%m/%Y')


@register.filter
def dias_texto(dias):
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        return ''
    if dias == 0:
        return 'Hoy'
    if dias == 1:
        return 'Mañana'
    if dias == -1:
        return 'Ayer'
    if dias > 0:
        return f'En {dias} días'
    return f'Hace {-dias} días'


@register.filter
def get(diccionario, clave):
    try:
        return diccionario.get(clave)
    except AttributeError:
        return None


@register.simple_tag(takes_context=True)
def activo(context, *nombres):
    """Devuelve 'is-active' si la vista actual coincide con 'namespace:nombre' o 'namespace:*'."""
    match = getattr(context.get('request'), 'resolver_match', None)
    if not match:
        return ''
    actual = f'{match.namespace}:{match.url_name}'
    for nombre in nombres:
        if nombre.endswith(':*') and match.namespace == nombre[:-2]:
            return 'is-active'
        if nombre == actual:
            return 'is-active'
    return ''


@register.simple_tag
def avatar(usuario, clase=''):
    if getattr(usuario, 'foto', None):
        try:
            return format_html('<span class="avatar {}"><img src="{}" alt=""></span>', clase, usuario.foto.url)
        except Exception:
            pass
    return format_html('<span class="avatar {}">{}</span>', clase, getattr(usuario, 'iniciales', '?'))
