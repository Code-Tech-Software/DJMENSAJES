"""
La cotización en PDF (ReportLab, sin dependencias del sistema): franja oscura con el logo de la agencia
(sus logos están pensados para fondo oscuro), cliente y evento, conceptos, totales, condiciones y el
enlace para aceptarla en línea.
"""
import logging
from io import BytesIO
from urllib.request import urlopen
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import Servicio

log = logging.getLogger(__name__)

MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre',
         'diciembre')
DIAS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')
OSCURO = colors.HexColor('#0E1726')
TEXTO = colors.HexColor('#1F2937')
GRIS = colors.HexColor('#6B7280')
SUAVE = colors.HexColor('#F3F5F9')
LINEA = colors.HexColor('#E4E8EF')
ALTO_FRANJA = 34 * mm


def dinero(valor):
    return f'${valor:,.2f}'


def fecha_larga(fecha, con_dia=False):
    texto = f'{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}'
    return f'{DIAS[fecha.weekday()]} {texto}' if con_dia else texto


def _color(hexadecimal):
    try:
        return colors.HexColor(hexadecimal or '#0098DA')
    except (ValueError, TypeError):
        return colors.HexColor('#0098DA')


def _tenue(color, cuanto=0.12):
    """El color de marca mezclado con blanco (fondos suaves)."""
    return colors.Color(1 - (1 - color.red) * cuanto, 1 - (1 - color.green) * cuanto, 1 - (1 - color.blue) * cuanto)


def _logo(archivo):
    """ImageReader del logo (almacenamiento local o Cloudinary); None si no hay o no se puede leer."""
    if not archivo:
        return None
    try:
        try:
            with archivo.open('rb') as f:
                datos = f.read()
        except Exception:  # almacenamiento remoto sin lectura directa: se descarga por su URL
            url = archivo.url
            if not url.startswith('http'):
                return None
            with urlopen(url, timeout=6) as r:
                datos = r.read()
        return ImageReader(BytesIO(datos))
    except Exception:
        log.warning('No se pudo leer el logo para el PDF', exc_info=True)
        return None


def _estilos(acento):
    base = ParagraphStyle('base', fontName='Helvetica', fontSize=9.5, leading=13, textColor=TEXTO)
    return {
        'base': base,
        'chico': ParagraphStyle('chico', parent=base, fontSize=8.2, leading=11, textColor=GRIS),
        'etiqueta': ParagraphStyle('etiqueta', parent=base, fontName='Helvetica-Bold', fontSize=7.5, leading=10,
                                   textColor=acento),
        'etiqueta_der': ParagraphStyle('etiqueta_der', parent=base, fontName='Helvetica-Bold', fontSize=7.5, leading=10,
                                       textColor=acento, alignment=TA_RIGHT),
        'fuerte': ParagraphStyle('fuerte', parent=base, fontName='Helvetica-Bold', fontSize=11, leading=14),
        'concepto': ParagraphStyle('concepto', parent=base, fontName='Helvetica-Bold'),
        'derecha': ParagraphStyle('derecha', parent=base, alignment=TA_RIGHT),
        'titulo': ParagraphStyle('titulo', parent=base, fontName='Helvetica-Bold', fontSize=10.5, leading=14,
                                 spaceBefore=4, spaceAfter=4),
    }


def generar_pdf(cotizacion, marca, url_publica):
    """Bytes del PDF de la cotización con la marca (agencia o sub-agencia) indicada."""
    acento = _color(marca.color)
    e = _estilos(acento)
    logo = _logo(marca.logo)
    hoy = timezone.localdate()
    buffer = BytesIO()

    def pagina(canvas, doc):
        ancho, alto = letter
        canvas.saveState()
        # Franja superior con el logo (o el nombre) y el folio
        canvas.setFillColor(OSCURO)
        canvas.rect(0, alto - ALTO_FRANJA, ancho, ALTO_FRANJA, stroke=0, fill=1)
        canvas.setFillColor(acento)
        canvas.rect(0, alto - ALTO_FRANJA - 2.2 * mm, ancho, 2.2 * mm, stroke=0, fill=1)
        x, centro = 16 * mm, alto - ALTO_FRANJA / 2
        if logo is not None:
            w, h = logo.getSize()
            escala = min(58 * mm / w, 17 * mm / h)
            canvas.drawImage(logo, x, centro - h * escala / 2, w * escala, h * escala, mask='auto')
        else:
            canvas.setFillColor(colors.white)
            canvas.setFont('Helvetica-Bold', 17)
            canvas.drawString(x, centro - 2 * mm, marca.nombre[:40])
            if marca.eslogan:
                canvas.setFont('Helvetica', 8.5)
                canvas.setFillColor(colors.HexColor('#B6C2D6'))
                canvas.drawString(x, centro - 7.5 * mm, marca.eslogan[:70])
        derecha = ancho - 16 * mm
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 16)
        canvas.drawRightString(derecha, centro + 2.5 * mm, 'COTIZACIÓN')
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.HexColor('#B6C2D6'))
        canvas.drawRightString(derecha, centro - 3.5 * mm, f'{cotizacion.folio}  ·  {fecha_larga(timezone.localtime(cotizacion.creado))}')
        # Pie: contacto de la agencia y número de página
        contacto = '  ·  '.join(x for x in (marca.nombre, marca.telefono, marca.email) if x)
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(GRIS)
        canvas.drawString(16 * mm, 10 * mm, contacto[:120])
        canvas.drawRightString(derecha, 10 * mm, f'Página {doc.page}')
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=ALTO_FRANJA + 10 * mm, bottomMargin=18 * mm,
                            title=f'Cotización {cotizacion.folio}', author=marca.nombre)
    ancho = letter[0] - 32 * mm
    historia = []

    # Cliente y evento
    inicio = timezone.localtime(cotizacion.fecha_evento)
    fin = timezone.localtime(cotizacion.fecha_fin)
    duracion = f'{cotizacion.duracion_horas.normalize():f}'
    cliente = [Paragraph('PARA', e['etiqueta']), Paragraph(escape(cotizacion.cliente_nombre), e['fuerte'])]
    for dato in (cotizacion.cliente_telefono, cotizacion.cliente_email):
        if dato:
            cliente.append(Paragraph(escape(dato), e['base']))
    evento = [Paragraph('EVENTO', e['etiqueta']), Paragraph(escape(cotizacion.titulo_evento), e['fuerte']),
              Paragraph(f'{escape(cotizacion.get_tipo_evento_display())} · {fecha_larga(inicio, con_dia=True).capitalize()}', e['base']),
              Paragraph(f'De {inicio:%H:%M} a {fin:%H:%M} h ({duracion} h)', e['base'])]
    lugar = ' · '.join(x for x in (escape(cotizacion.lugar), f'{cotizacion.num_invitados} invitados' if cotizacion.num_invitados else '') if x)
    if lugar:
        evento.append(Paragraph(lugar, e['base']))
    datos = Table([[cliente, evento]], colWidths=[ancho * 0.42, ancho * 0.58])
    datos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), SUAVE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LINEAFTER', (0, 0), (0, 0), 0.6, LINEA),
    ]))
    historia += [datos, Spacer(0, 7 * mm)]

    # Conceptos
    filas = [[Paragraph('CONCEPTO', e['etiqueta']), Paragraph('CANT.', e['etiqueta']),
              Paragraph('PRECIO', e['etiqueta_der']), Paragraph('IMPORTE', e['etiqueta_der'])]]
    for c in cotizacion.conceptos.all():
        texto = f'{escape(c.descripcion)}'
        if c.detalle:
            texto += f'<br/><font name="Helvetica" size="8.2" color="#6B7280">{escape(c.detalle)}</font>'
        cantidad = f'{c.cantidad.normalize():f}' + (' h' if c.unidad == Servicio.Unidad.HORA else '')
        filas.append([Paragraph(texto, e['concepto']), Paragraph(cantidad, e['base']),
                      Paragraph(dinero(c.precio_unitario), e['derecha']), Paragraph(dinero(c.importe), e['derecha'])])
    tabla = Table(filas, colWidths=[ancho * 0.55, ancho * 0.11, ancho * 0.17, ancho * 0.17], repeatRows=1)
    estilo = [
        ('BACKGROUND', (0, 0), (-1, 0), _tenue(acento)), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, LINEA),
    ]
    tabla.setStyle(TableStyle(estilo))
    historia += [tabla, Spacer(0, 4 * mm)]

    # Totales
    totales = [['Subtotal', dinero(cotizacion.subtotal)]]
    if cotizacion.descuento:
        totales.append(['Descuento', f'-{dinero(cotizacion.descuento)}'])
    totales.append(['Total', dinero(cotizacion.total)])
    if cotizacion.anticipo_porcentaje:
        totales.append([f'Anticipo para apartar la fecha ({cotizacion.anticipo_porcentaje}%)', dinero(cotizacion.anticipo)])
    fila_total = len(totales) - (2 if cotizacion.anticipo_porcentaje else 1)
    caja = Table(totales, colWidths=[ancho * 0.36, ancho * 0.2], hAlign='RIGHT')
    caja.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 9.5), ('TEXTCOLOR', (0, 0), (-1, -1), TEXTO),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'), ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('FONT', (0, fila_total), (-1, fila_total), 'Helvetica-Bold', 13),
        ('TEXTCOLOR', (1, fila_total), (1, fila_total), acento),
        ('LINEABOVE', (0, fila_total), (-1, fila_total), 1, acento),
        ('TOPPADDING', (0, fila_total), (-1, fila_total), 7), ('BOTTOMPADDING', (0, fila_total), (-1, fila_total), 7),
        ('TEXTCOLOR', (0, fila_total + 1), (-1, -1), GRIS),
    ]))
    historia += [caja, Spacer(0, 6 * mm)]

    # Condiciones, vigencia y enlace para aceptar
    bloque = []
    lineas = [x.strip(' -•\t') for x in cotizacion.condiciones.splitlines() if x.strip(' -•\t')]
    if lineas:
        bloque.append(Paragraph('Condiciones', e['titulo']))
        bloque += [Paragraph(f'•&nbsp;&nbsp;{escape(x)}', e['chico']) for x in lineas]
        bloque.append(Spacer(0, 4 * mm))
    vencida = cotizacion.vigencia < hoy
    aviso = (f'<b>Vigencia:</b> {"venció" if vencida else "válida hasta"} el {fecha_larga(cotizacion.vigencia)}.'
             f'<br/><b>Acéptala en línea:</b> <a href="{escape(url_publica)}" color="#{acento.hexval()[2:]}">{escape(url_publica)}</a>')
    nota = Table([[Paragraph(aviso, e['base'])]], colWidths=[ancho])
    nota.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _tenue(acento, 0.08)), ('LINEBEFORE', (0, 0), (0, -1), 2.5, acento),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]))
    bloque.append(nota)
    historia.append(KeepTogether(bloque))

    doc.build(historia, onFirstPage=pagina, onLaterPages=pagina)
    return buffer.getvalue()


def nombre_archivo(cotizacion):
    seguro = ''.join(c for c in cotizacion.titulo_evento if c.isalnum() or c in ' -_&')[:40].strip()
    return f'Cotizacion {cotizacion.folio} {seguro}.pdf'.replace('  ', ' ')
