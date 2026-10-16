"""Utilidades compartidas por todas las apps."""
import io
import secrets
import string

import qrcode
import qrcode.image.svg
from django.utils.text import slugify

ALFABETO_CODIGO = string.ascii_lowercase.replace('l', '').replace('o', '') + '23456789'


def generar_codigo(longitud=7):
    """Código corto, legible y sin caracteres ambiguos (para URLs y QR)."""
    return ''.join(secrets.choice(ALFABETO_CODIGO) for _ in range(longitud))


def generar_token(bytes_=18):
    return secrets.token_urlsafe(bytes_)


def slug_unico(texto, modelo, campo='slug', max_largo=40):
    base = slugify(texto)[:max_largo].strip('-') or 'evento'
    while True:
        candidato = f'{base}-{generar_codigo(4)}'
        if not modelo.objects.filter(**{campo: candidato}).exists():
            return candidato


def qr_svg(datos, color='#0e1726'):
    """Devuelve el QR como SVG (nítido a cualquier tamaño, sin archivos)."""
    qr = qrcode.QRCode(border=1, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(datos)
    qr.make(fit=True)
    imagen = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    buffer = io.BytesIO()
    imagen.save(buffer)
    svg = buffer.getvalue().decode('utf-8')
    svg = svg.split('?>', 1)[-1].strip()  # quita la cabecera <?xml ?>
    return svg.replace('fill="#000000"', f'fill="{color}"').replace(
        '<svg ', '<svg preserveAspectRatio="xMidYMid meet" ', 1)


def ip_cliente(request):
    reenviada = request.META.get('HTTP_X_FORWARDED_FOR')
    if reenviada:
        return reenviada.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def iniciales(texto, maximo=2):
    partes = [p for p in (texto or '').replace('&', ' ').split() if p[:1].isalnum()]
    return ''.join(p[0] for p in partes[:maximo]).upper() or '?'
