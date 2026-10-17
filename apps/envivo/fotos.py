"""Procesa las fotos que mandan los invitados.

El celular ya las reduce antes de subirlas, pero aquí se valida todo de nuevo:
que sea una imagen real, se endereza según el EXIF, se reduce, se guarda como JPEG
sin metadatos (se quita la ubicación GPS) y se genera una miniatura para las listas.
"""
from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_MB = 15
LADO_FOTO = 1600
LADO_MINIATURA = 480


class FotoInvalida(Exception):
    """La foto no se puede usar; el mensaje es apto para mostrarse al invitado."""


def _a_jpeg(imagen, calidad):
    buffer = BytesIO()
    imagen.save(buffer, 'JPEG', quality=calidad, optimize=True, progressive=True)
    return ContentFile(buffer.getvalue())


def procesar_foto(archivo):
    """Devuelve (nombre_base, foto, miniatura, ancho, alto) listos para guardarse."""
    if not archivo:
        raise FotoInvalida('Elige una foto para enviar.')
    if archivo.size > MAX_MB * 1024 * 1024:
        raise FotoInvalida(f'La foto pesa más de {MAX_MB} MB. Intenta con otra.')
    try:
        Image.open(archivo).verify()
        archivo.seek(0)
        imagen = ImageOps.exif_transpose(Image.open(archivo))
        imagen.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        raise FotoInvalida('No pudimos leer la imagen. Intenta con otra foto.')

    # Transparencias (PNG) sobre blanco; todo termina en RGB para JPEG
    if imagen.mode in ('RGBA', 'LA', 'P'):
        imagen = imagen.convert('RGBA')
        fondo = Image.new('RGB', imagen.size, (255, 255, 255))
        fondo.paste(imagen, mask=imagen.getchannel('A'))
        imagen = fondo
    elif imagen.mode != 'RGB':
        imagen = imagen.convert('RGB')

    grande = imagen.copy()
    grande.thumbnail((LADO_FOTO, LADO_FOTO), Image.LANCZOS)
    mini = imagen.copy()
    mini.thumbnail((LADO_MINIATURA, LADO_MINIATURA), Image.LANCZOS)
    return uuid4().hex[:20], _a_jpeg(grande, 85), _a_jpeg(mini, 78), grande.width, grande.height
