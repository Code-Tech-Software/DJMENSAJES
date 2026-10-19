"""
Carga datos de demostración para probar la plataforma en local.

    python manage.py datos_demo

Crea el usuario `demo` (contraseña `demo1234`), colaboradores, banners con fondos
generados, eventos (pasados, en curso y próximos), una invitación con invitados y
mensajes en vivo. Solo funciona con DEBUG=True salvo que se use --forzar.
"""
import io
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFilter

from apps.banners.models import Banner
from apps.colaboradores.models import Colaborador
from apps.core.models import Agencia, Plan
from apps.cuentas.models import Usuario
from apps.envivo.models import Mensaje
from apps.eventos.models import ActividadItinerario, Evento, Pago
from apps.invitaciones.models import FotoInvitacion, Invitacion, Invitado, Mencion, Ubicacion

USUARIO_DEMO = 'demo'
CLAVE_DEMO = 'demo1234'


def _fondo(ancho, alto, colores, semilla):
    """Imagen con degradado y destellos tipo bokeh."""
    aleatorio = random.Random(semilla)
    img = Image.new('RGB', (ancho, alto), colores[0])
    dibujo = ImageDraw.Draw(img)
    for y in range(alto):
        t = y / alto
        r = int(colores[0][0] * (1 - t) + colores[1][0] * t)
        g = int(colores[0][1] * (1 - t) + colores[1][1] * t)
        b = int(colores[0][2] * (1 - t) + colores[1][2] * t)
        dibujo.line([(0, y), (ancho, y)], fill=(r, g, b))
    capa = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))
    luces = ImageDraw.Draw(capa)
    for _ in range(38):
        radio = aleatorio.randint(int(min(ancho, alto) * .02), int(min(ancho, alto) * .12))
        x, y = aleatorio.randint(0, ancho), aleatorio.randint(0, alto)
        color = colores[2] + (aleatorio.randint(40, 120),)
        luces.ellipse([x - radio, y - radio, x + radio, y + radio], fill=color)
    capa = capa.filter(ImageFilter.GaussianBlur(min(ancho, alto) * .02))
    img = Image.alpha_composite(img.convert('RGBA'), capa).convert('RGB')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=86)
    return ContentFile(buffer.getvalue())


class Command(BaseCommand):
    help = 'Carga datos de demostración (solo para desarrollo).'

    def add_arguments(self, parser):
        parser.add_argument('--forzar', action='store_true', help='Permite ejecutarlo con DEBUG=False.')

    def handle(self, *args, **opciones):
        if not settings.DEBUG and not opciones['forzar']:
            raise CommandError('Por seguridad solo se ejecuta con DEBUG=True (usa --forzar si estás seguro).')
        if Evento.objects.filter(nombre_evento='Ana & Luis').exists():
            self.stdout.write(self.style.WARNING('Los datos de demostración ya existen.'))
            return

        ahora = timezone.now()
        hoy = timezone.localdate()
        aleatorio = random.Random(7)

        # --- Planes de EventPro y la agencia (cliente) a la que pertenece todo lo demás
        for orden, (nombre, precio, eventos, usuarios, subagencias) in enumerate([
                ('Básico', 499, 4, 2, 1), ('Pro', 999, 15, 6, 5), ('Agencia', 1999, None, None, None)]):
            Plan.objects.get_or_create(nombre=nombre, defaults={
                'precio_mensual': precio, 'max_eventos_mes': eventos, 'max_usuarios': usuarios,
                'max_colaboradores': subagencias, 'orden': orden})
        agencia, _ = Agencia.objects.get_or_create(slug='grupo-em', defaults={'nombre': 'Grupo EM'})

        # --- Equipo
        admin, creado = Usuario.objects.get_or_create(username=USUARIO_DEMO, defaults={
            'agencia': agencia,
            'first_name': 'Luis', 'last_name': 'Ramírez', 'email': 'demo@eventpro.local',
            'rol': Usuario.Rol.ADMIN, 'is_staff': True, 'is_superuser': True, 'cargo': 'Director general',
        })
        if creado:
            admin.set_password(CLAVE_DEMO)
            admin.save()

        # --- Colaboradores
        logo = settings.BASE_DIR / 'static' / 'img' / 'logo-eventpro.png'
        espectaculares = Colaborador.objects.create(agencia=agencia, 
            nombre='Eventos Espectaculares', tipo='sonido', ciudad='Puebla, Pue.', responsable='Marco Ruiz',
            telefono='2221234567', whatsapp='2221234567', email='hola@espectaculares.mx', color_marca='#0098DA',
            eslogan='Hacemos vibrar tu fiesta', instagram='https://instagram.com/eventpro',
            facebook='https://facebook.com/eventpro', descripcion='Audio, iluminación y DJ para bodas, XV años y eventos sociales.',
        )
        with open(logo, 'rb') as f:
            espectaculares.logo_principal.save('espectaculares.png', File(f), save=True)
        palmas = Colaborador.objects.create(agencia=agencia, 
            nombre='Jardín Las Palmas', tipo='salon', ciudad='Cholula, Pue.', responsable='Andrea Torres',
            telefono='2229876543', whatsapp='2229876543', color_marca='#10A37F', eslogan='El jardín de tus sueños',
        )
        Colaborador.objects.create(agencia=agencia, nombre='Luz Studio', tipo='foto', ciudad='CDMX', responsable='Diego Paz', color_marca='#D43FE6')

        Usuario.objects.get_or_create(username='sofia', defaults={
            'agencia': agencia,
            'first_name': 'Sofía', 'last_name': 'Méndez', 'rol': Usuario.Rol.COORDINADOR, 'cargo': 'Coordinadora de eventos'})
        Usuario.objects.get_or_create(username='dj.marco', defaults={
            'agencia': agencia,
            'first_name': 'Marco', 'last_name': 'Ruiz', 'rol': Usuario.Rol.COLABORADOR, 'colaborador': espectaculares, 'cargo': 'DJ residente'})

        # --- Banners con fondos generados
        paletas = [
            ('Dorado elegante', 'boda', [(40, 28, 16), (120, 88, 48), (255, 214, 150)]),
            ('Noche neón', 'fiesta', [(14, 6, 32), (60, 12, 90), (224, 64, 251)]),
            ('Azul profundo', 'general', [(4, 18, 40), (0, 92, 150), (120, 210, 255)]),
            ('Rosa XV', 'xv', [(60, 10, 40), (190, 60, 130), (255, 180, 220)]),
        ]
        banners = []
        for i, (nombre, categoria, colores) in enumerate(paletas):
            banner = Banner(agencia=agencia, nombre=nombre, categoria=categoria, descripcion=f'Fondo {nombre.lower()} generado para la demostración.')
            banner.fondo_movil.save(f'demo-{i}-movil.jpg', _fondo(720, 1280, colores, i), save=False)
            banner.fondo_pantalla.save(f'demo-{i}-pantalla.jpg', _fondo(1600, 900, colores, i + 10), save=False)
            banner.portada.save(f'demo-{i}-portada.jpg', _fondo(1200, 800, colores, i + 20), save=False)
            banner.save()
            banners.append(banner)

        def fecha(dias, hora=19):
            return timezone.make_aware(datetime.combine(hoy + timedelta(days=dias), time(hora, 0)))

        # --- Eventos
        boda = Evento.objects.create(agencia=agencia, 
            nombre_evento='Ana & Luis', tipo_evento='boda', colaborador=espectaculares, banner=banners[0], creado_por=admin,
            fecha_inicio_evento=fecha(12, 17), fecha_fin_evento=fecha(13, 2), lugar='Jardín Las Palmas',
            direccion='Av. Las Palmas 120, Cholula, Puebla', cliente_nombre='Ana García', cliente_telefono='2225550101',
            precio_total=Decimal('48500'), num_invitados=220, password_vip='padrinos',
            servicios='Audio profesional\nDJ 7 horas\nPista iluminada 6x6\nPantalla y proyector\nInvitación digital con RSVP',
            mensaje_bienvenida='¡Gracias por acompañarnos! Pide tu canción y déjanos un saludo 💛',
        )
        en_curso = Evento.objects.create(agencia=agencia, 
            nombre_evento='Sofía', tipo_evento='quinse', colaborador=espectaculares, banner=banners[3], creado_por=admin,
            fecha_inicio_evento=ahora - timedelta(hours=2), fecha_fin_evento=ahora + timedelta(hours=4),
            lugar='Salón Cristal', direccion='Blvd. 5 de Mayo 300, Puebla', cliente_nombre='Familia Hernández',
            precio_total=Decimal('35000'), num_invitados=180, password_vip='sofia15', cooldown=1, moderar_pantalla=True,
        )
        otros = [
            ('Graduación TEC 2026', 'graduacion', 3, 21, banners[2], 'cotizacion', Decimal('22000')),
            ('Cumple 30 de Diego', 'cumple', 1, 20, banners[1], 'confirmado', Decimal('12000')),
            ('Bautizo de Mateo', 'bautizo', 19, 14, None, 'confirmado', Decimal('9500')),
            ('Fiesta de fin de año', 'corporativo', 40, 20, banners[2], 'cotizacion', Decimal('65000')),
            ('Aniversario 25 · Rosa & Juan', 'aniversario', 27, 19, banners[0], 'confirmado', Decimal('18000')),
            ('Valeria', 'quinse', -15, 20, banners[3], 'confirmado', Decimal('30000')),
            ('Boda Karla & Iván', 'boda', -40, 18, banners[0], 'confirmado', Decimal('52000')),
            ('Neón Party', 'fiesta', -70, 22, banners[1], 'confirmado', Decimal('15000')),
        ]
        for nombre, tipo, dias, hora, banner, etapa, precio in otros:
            Evento.objects.create(agencia=agencia, 
                nombre_evento=nombre, tipo_evento=tipo, colaborador=aleatorio.choice([espectaculares, palmas, None]),
                banner=banner, creado_por=admin, etapa=etapa, fecha_inicio_evento=fecha(dias, hora),
                fecha_fin_evento=fecha(dias, hora) + timedelta(hours=6), lugar=aleatorio.choice(['Salón Cristal', 'Hacienda San Juan', 'Terraza Sky']),
                precio_total=precio, cliente_nombre=aleatorio.choice(['Laura Pérez', 'Carlos Díaz', 'Mariana López']),
            )

        # --- Itinerario y pagos de la boda
        for hora, titulo, icono, desc in [
            (time(17, 0), 'Ceremonia religiosa', 'ceremonia', 'Parroquia de San Pedro'),
            (time(19, 0), 'Recepción', 'recepcion', 'Jardín Las Palmas'),
            (time(20, 30), 'Cena', 'cena', ''),
            (time(21, 30), 'Vals de los novios', 'vals', ''),
            (time(22, 0), '¡A bailar!', 'fiesta', ''),
        ]:
            ActividadItinerario.objects.create(evento=boda, hora=hora, titulo=titulo, icono=icono, descripcion=desc)
        Pago.objects.create(evento=boda, monto=Decimal('15000'), fecha=hoy - timedelta(days=60), metodo='transferencia', referencia='Anticipo', registrado_por=admin)
        Pago.objects.create(evento=boda, monto=Decimal('10000'), fecha=hoy - timedelta(days=20), metodo='efectivo', referencia='Segundo abono', registrado_por=admin)
        Pago.objects.create(evento=en_curso, monto=Decimal('35000'), fecha=hoy - timedelta(days=5), metodo='tarjeta', referencia='Liquidación', registrado_por=admin)

        # --- Invitación de la boda
        invitacion = Invitacion.objects.create(
            evento=boda, slug='ana-y-luis-demo', plantilla='elegante', color_principal='#B08D57', publicada=True,
            nombres='Ana & Luis', frase='Hay momentos en la vida que son especiales por sí solos, pero compartirlos con las personas que quieres los hace inolvidables.',
            dress_code='Formal · evitar blanco', mesa_regalos='Liverpool · Evento 51234567\nLluvia de sobres',
            hashtag='#AnaYLuis2026', aviso='Evento solo para adultos', texto_sobre='Con mucho cariño, para ti',
            fecha_limite_rsvp=hoy + timedelta(days=5), rsvp_abierto=False,
        )
        for orden, (titulo, nombres) in enumerate([
            ('Padres de la novia', 'Rosa Martínez\nJuan García'),
            ('Padres del novio', 'Laura Gómez\nPedro Ramírez'),
            ('Padrinos de velación', 'Claudia Ruiz y Fernando Díaz'),
            ('Padrinos de anillos', 'Sofía Torres y Diego Paz'),
        ]):
            Mencion.objects.create(invitacion=invitacion, titulo=titulo, nombres=nombres, orden=orden)
        Ubicacion.objects.create(
            invitacion=invitacion, tipo='religiosa', lugar='Parroquia de San Pedro Apóstol', hora=time(17, 0), orden=0,
            direccion='Calle 4 Norte 2, Centro, San Pedro Cholula', notas='Llegar 15 minutos antes',
        )
        Ubicacion.objects.create(
            invitacion=invitacion, tipo='recepcion', lugar='Jardín Las Palmas', hora=time(19, 0), orden=1,
            direccion='Av. Las Palmas 120, Cholula, Puebla', notas='Estacionamiento con valet',
        )
        for i, colores in enumerate([[(60, 40, 20), (170, 130, 80), (255, 230, 180)], [(30, 40, 30), (120, 150, 110), (240, 250, 220)],
                                     [(70, 30, 40), (180, 110, 120), (255, 220, 225)], [(20, 30, 50), (90, 120, 160), (220, 235, 255)],
                                     [(50, 35, 25), (150, 110, 70), (250, 220, 170)]]):
            foto = FotoInvitacion(invitacion=invitacion, orden=i)
            foto.imagen.save(f'demo-galeria-{i}.jpg', _fondo(900, 900, colores, 40 + i), save=True)
        familias = ['Familia Pérez López', 'Familia García', 'Tía Rosy', 'Carlos Mendoza', 'Familia Ruiz', 'Mariana y Toño',
                    'Familia Hernández', 'Los primos Díaz', 'Abuelita Carmen', 'Jorge Salinas', 'Familia Torres', 'Paola Méndez',
                    'Familia Castillo', 'Ricardo y Ana', 'Familia Vega', 'Lucía Morales', 'Familia Navarro', 'Pepe y Lupita',
                    'Familia Ortega', 'Sandra Ríos', 'Familia Cruz', 'Alberto Fuentes']
        grupos = ['Familia novia', 'Familia novio', 'Amigos', 'Trabajo']
        for i, nombre in enumerate(familias):
            pases = aleatorio.choice([1, 2, 2, 3, 4, 5])
            estado = aleatorio.choice(['confirmado', 'confirmado', 'confirmado', 'pendiente', 'pendiente', 'rechazado'])
            invitado = Invitado(
                evento=boda, nombre=nombre, pases=pases, grupo=grupos[i % 4], mesa=str(aleatorio.randint(1, 22)),
                telefono=f'222{aleatorio.randint(1000000, 9999999)}', estado=estado,
                pases_confirmados=pases if estado == 'confirmado' else 0,
                enviada_en=ahora - timedelta(days=aleatorio.randint(3, 15)) if i < 18 else None,
            )
            if estado != 'pendiente':
                invitado.respondido_en = ahora - timedelta(hours=aleatorio.randint(1, 200))
                invitado.vista_en = invitado.respondido_en - timedelta(minutes=10)
                invitado.mensaje = aleatorio.choice(['', '¡Felicidades! Ahí estaremos 🎉', '¡Qué emoción! Los queremos', ''])
            elif i % 3 == 0:
                invitado.vista_en = ahora - timedelta(hours=aleatorio.randint(1, 48))
            invitado.save()

        # --- Mensajes en vivo del evento en curso
        canciones = [('Tusa', 'Karol G'), ('Payaso de Rodeo', 'Caballo Dorado'), ('Despechá', 'Rosalía'),
                     ('La Chona', 'Los Tucanes de Tijuana'), ('Ella Baila Sola', 'Eslabón Armado'), ('Vivir Mi Vida', 'Marc Anthony'),
                     ('El Triste', 'José José'), ('Dancing Queen', 'ABBA')]
        saludos = [('Sofía', '¡Felicidades princesa! Que este día sea inolvidable ✨'), ('Los papás', '¡Estamos muy orgullosos de ti!'),
                   ('Sofía', '¡Que viva la quinceañera! 🎉'), ('la mesa 4', 'Los primos les mandan un saludo enorme'),
                   ('todos', '¡Qué gran fiesta! Gracias por invitarnos')]
        nombres = ['Mesa 3', 'Andrea', 'Tío Beto', 'Valeria', 'Los primos', 'Karla', 'Mesa 9', 'Diego']
        minutos = 110
        for i, (cancion, artista) in enumerate(canciones):
            minutos -= aleatorio.randint(5, 12)
            m = Mensaje.objects.create(evento=en_curso, nombre=nombres[i % len(nombres)], tipo='cancion', mensaje=cancion,
                                       artista=artista, vip=i in (2, 6), estatus='atendido' if i < 4 else 'pendiente')
            Mensaje.objects.filter(pk=m.pk).update(fecha_creacion=ahora - timedelta(minutes=max(minutos, 2)))
        for i, (para, texto) in enumerate(saludos):
            m = Mensaje.objects.create(evento=en_curso, nombre=nombres[(i + 3) % len(nombres)], tipo='saludo', mensaje=texto,
                                       destinatario=para, vip=i == 1, en_pantalla=i < 3, estatus='atendido' if i < 2 else 'pendiente')
            Mensaje.objects.filter(pk=m.pk).update(fecha_creacion=ahora - timedelta(minutes=60 - i * 9))

        # Fotos de los invitados: las primeras ya aprobadas (pantalla y álbum), las últimas por revisar
        fotos = [('Andrea', '¡La pista está que arde! 🔥', ((214, 51, 132), (63, 31, 120), (255, 196, 120))),
                 ('Tío Beto', 'Brindis con toda la familia 🥂', ((24, 46, 92), (198, 120, 54), (255, 226, 160))),
                 ('Valeria', '', ((12, 74, 110), (130, 40, 160), (120, 220, 255))),
                 ('Mesa 9', 'La mejor mesa de la noche', ((120, 30, 60), (250, 140, 60), (255, 230, 170))),
                 ('Karla', 'Sofía brillando ✨', ((40, 20, 90), (210, 70, 160), (255, 170, 230))),
                 ('Los primos', 'Foto de primos 📸', ((10, 60, 70), (40, 160, 140), (200, 255, 220)))]
        for i, (nombre, pie, colores) in enumerate(fotos):
            ancho, alto = (1200, 900) if i % 3 else (900, 1200)
            m = Mensaje(evento=en_curso, nombre=nombre, tipo='foto', mensaje=pie, foto_ancho=ancho, foto_alto=alto,
                        estatus='atendido' if i < 4 else 'pendiente', en_pantalla=i < 4)
            m.foto.save(f'demo-foto-{i}.jpg', _fondo(ancho, alto, colores, 300 + i), save=False)
            m.miniatura.save(f'demo-foto-{i}.jpg', _fondo(ancho // 3, alto // 3, colores, 300 + i), save=False)
            m.save()
            Mensaje.objects.filter(pk=m.pk).update(fecha_creacion=ahora - timedelta(minutes=50 - i * 7))

        self.stdout.write(self.style.SUCCESS(
            f'Datos de demostración listos. Inicia sesión con usuario "{USUARIO_DEMO}" y contraseña "{CLAVE_DEMO}".'))
