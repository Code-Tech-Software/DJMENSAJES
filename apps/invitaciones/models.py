from urllib.parse import quote

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone

from apps.core.utils import generar_token


def almacenamiento_audio():
    """Cloudinary guarda el audio como recurso de video; en local se usa el disco."""
    if settings.CLOUDINARY_ACTIVO:
        from cloudinary_storage.storage import VideoMediaCloudinaryStorage
        return VideoMediaCloudinaryStorage()
    from django.core.files.storage import default_storage
    return default_storage


class Invitacion(models.Model):
    """Invitación digital de un evento (una por evento)."""

    class Plantilla(models.TextChoices):
        ELEGANTE = 'elegante', 'Elegante'
        JARDIN = 'jardin', 'Jardín'
        MODERNA = 'moderna', 'Moderna'
        FIESTA = 'fiesta', 'Neón'

    class Tipografia(models.TextChoices):
        AUTO = 'auto', 'La de la plantilla'
        SCRIPT = 'script', 'Manuscrita'
        CALIGRAFIA = 'caligrafia', 'Caligrafía fina'
        SERIF = 'serif', 'Clásica'
        MODERNA = 'moderna', 'Moderna'
        IMPACTO = 'impacto', 'Impacto'

    COLORES_PLANTILLA = {
        'elegante': '#B08D57',
        'jardin': '#7A9471',
        'moderna': '#0098DA',
        'fiesta': '#E040FB',
    }

    PALETAS = {
        'elegante': ['#B08D57', '#C9A227', '#9C7C5B', '#8E6C88', '#4A5D7E', '#2F2F2F'],
        'jardin': ['#7A9471', '#5E7D5A', '#C98B8B', '#B49A6B', '#8A9BB0', '#6E6A8E'],
        'moderna': ['#0098DA', '#111827', '#E4572E', '#16A34A', '#7C3AED', '#DB2777'],
        'fiesta': ['#E040FB', '#00E5FF', '#FF3D7F', '#7C4DFF', '#FFD60A', '#39FF14'],
    }

    evento = models.OneToOneField('eventos.Evento', on_delete=models.CASCADE, related_name='invitacion')
    slug = models.SlugField(max_length=60, unique=True)
    plantilla = models.CharField(max_length=20, choices=Plantilla.choices, default=Plantilla.ELEGANTE)
    color_principal = models.CharField('color principal', max_length=7, default='#B08D57')
    tipografia = models.CharField(
        'letra de los nombres', max_length=20, choices=Tipografia.choices, default=Tipografia.AUTO,
    )
    texto_sobre = models.CharField(
        'texto del sobre', max_length=120, blank=True,
        help_text='Aparece bajo el sobre antes de abrirlo. Ej. "Tienes una invitación especial".',
    )

    titulo = models.CharField('encabezado', max_length=120, blank=True, help_text='Ej. "¡Nos casamos!"')
    nombres = models.CharField(
        'nombres destacados', max_length=150, blank=True,
        help_text='Ej. "Ana & Luis". Si se deja vacío se usa el nombre del evento.',
    )
    frase = models.TextField('frase o mensaje', blank=True)
    hashtag = models.CharField(max_length=60, blank=True, help_text='Para que tus invitados compartan fotos. Ej. #AnaYLuis2026')
    aviso = models.CharField(
        'aviso importante', max_length=160, blank=True,
        help_text='Ej. "Evento solo para adultos" o "Favor de llegar 15 minutos antes".',
    )
    portada = models.ImageField(
        upload_to='invitaciones/', blank=True, null=True,
        help_text='Si no subes una, se usa la portada del fondo visual del evento.',
    )
    dress_code = models.CharField('código de vestimenta', max_length=120, blank=True)
    mesa_regalos = models.TextField('mesa de regalos', blank=True)
    regalos_url = models.URLField('enlace de mesa de regalos', blank=True)
    musica = models.FileField(
        'música de fondo', upload_to='invitaciones/musica/', storage=almacenamiento_audio, blank=True,
        validators=[FileExtensionValidator(['mp3', 'm4a', 'aac', 'ogg', 'wav'])],
        help_text='MP3 de hasta 10 MB. Empieza a sonar al abrir el sobre.',
    )
    musica_titulo = models.CharField('nombre de la canción', max_length=120, blank=True)
    fecha_limite_rsvp = models.DateField('confirmar antes del', null=True, blank=True)

    rsvp_abierto = models.BooleanField(
        'confirmación abierta', default=False,
        help_text='Permite confirmar desde el enlace general sin estar en la lista.',
    )
    mostrar_contador = models.BooleanField('mostrar cuenta regresiva', default=True)
    mostrar_itinerario = models.BooleanField('mostrar itinerario', default=True)
    mostrar_mapa = models.BooleanField('mostrar lugares y mapas', default=True)
    publicada = models.BooleanField(default=False)
    visitas = models.PositiveIntegerField(default=0, editable=False)
    # Enlace privado para que los anfitriones administren su lista de invitados (vacío = desactivado)
    token_anfitriones = models.CharField(
        'enlace de los anfitriones', max_length=40, unique=True, null=True, blank=True, editable=False,
    )

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'invitación'
        verbose_name_plural = 'invitaciones'

    def __str__(self):
        return f'Invitación · {self.evento}'

    def get_absolute_url(self):
        return reverse('invitacion_publica:general', args=[self.slug])

    def url_anfitriones(self):
        return reverse('anfitriones:panel', args=[self.token_anfitriones]) if self.token_anfitriones else ''

    @property
    def nombres_visibles(self):
        return self.nombres or self.evento.nombre_evento

    @property
    def titulo_visible(self):
        if self.titulo:
            return self.titulo
        return {
            'boda': '¡Nos casamos!',
            'quinse': 'Mis XV Años',
            'cumple': '¡Celebremos juntos!',
            'bautizo': 'Mi Bautizo',
            'graduacion': '¡Me gradúo!',
            'aniversario': 'Nuestro aniversario',
            'corporativo': 'Te invitamos',
        }.get(self.evento.tipo_evento, '¡Estás invitado!')

    @property
    def imagen_portada(self):
        if self.portada:
            return self.portada
        banner = self.evento.banner
        return banner.imagen_portada if banner else None

    @property
    def rsvp_vencido(self):
        return bool(self.fecha_limite_rsvp and timezone.localdate() > self.fecha_limite_rsvp)


class Ubicacion(models.Model):
    """Lugar de una parte del evento: ceremonia religiosa, civil, recepción, fiesta…"""

    class Tipo(models.TextChoices):
        RELIGIOSA = 'religiosa', 'Ceremonia religiosa'
        CIVIL = 'civil', 'Ceremonia civil'
        RECEPCION = 'recepcion', 'Recepción'
        FIESTA = 'fiesta', 'Fiesta'
        COCTEL = 'coctel', 'Cóctel'
        OTRO = 'otro', 'Otro'

    invitacion = models.ForeignKey(Invitacion, on_delete=models.CASCADE, related_name='ubicaciones')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.RECEPCION)
    titulo = models.CharField(
        'nombre de esta parte', max_length=80, blank=True,
        help_text='Opcional. Ej. "Misa de acción de gracias". Si lo dejas vacío se usa el tipo.',
    )
    lugar = models.CharField('lugar', max_length=150, help_text='Ej. Parroquia de San Pedro Apóstol')
    fecha = models.DateField(null=True, blank=True, help_text='Vacío = el día del evento.')
    hora = models.TimeField(null=True, blank=True)
    direccion = models.CharField('dirección', max_length=255, blank=True)
    url_mapa = models.URLField('enlace de Google Maps', blank=True)
    notas = models.CharField('indicaciones', max_length=200, blank=True,
                             help_text='Ej. "Estacionamiento en la parte trasera".')
    foto = models.ImageField(upload_to='invitaciones/lugares/', blank=True, null=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'hora', 'id']
        verbose_name = 'lugar'
        verbose_name_plural = 'lugares'

    def __str__(self):
        return f'{self.nombre_visible} · {self.lugar}'

    @property
    def nombre_visible(self):
        return self.titulo or self.get_tipo_display()

    @property
    def fecha_visible(self):
        return self.fecha or timezone.localdate(self.invitacion.evento.fecha_inicio_evento)

    @property
    def mapa(self):
        if self.url_mapa:
            return self.url_mapa
        consulta = ', '.join(x for x in [self.lugar, self.direccion] if x)
        return f'https://www.google.com/maps/search/?api=1&query={quote(consulta)}'


class Mencion(models.Model):
    """Personas especiales: padres, padrinos de anillos, lazo, arras, damas…"""

    SUGERENCIAS = [
        'Con la bendición de nuestros padres', 'Padres de la novia', 'Padres del novio', 'Mis padres',
        'Mis padrinos', 'Padrinos de velación', 'Padrinos de anillos', 'Padrinos de lazo',
        'Padrinos de arras', 'Padrinos de ramo', 'Damas de honor', 'Chambelanes',
    ]

    invitacion = models.ForeignKey(Invitacion, on_delete=models.CASCADE, related_name='menciones')
    titulo = models.CharField(max_length=80, help_text='Ej. "Padrinos de anillos".')
    nombres = models.TextField(help_text='Un nombre o pareja por línea.')
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = 'mención'
        verbose_name_plural = 'menciones'

    def __str__(self):
        return self.titulo

    @property
    def lista(self):
        return [n.strip() for n in self.nombres.splitlines() if n.strip()]


class FotoInvitacion(models.Model):
    invitacion = models.ForeignKey(Invitacion, on_delete=models.CASCADE, related_name='fotos')
    imagen = models.ImageField(upload_to='invitaciones/galeria/')
    orden = models.PositiveSmallIntegerField(default=0)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = 'foto'
        verbose_name_plural = 'galería'

    def __str__(self):
        return f'Foto {self.pk} · {self.invitacion}'


class InvitadoQuerySet(models.QuerySet):
    def resumen(self):
        # Los alias no pueden llamarse igual que los campos ("pases"), por eso se renombran al final
        datos = self.aggregate(
            n_total=Count('id'),
            suma_pases=Sum('pases'),
            n_confirmados=Count('id', filter=Q(estado='confirmado')),
            suma_confirmados=Sum('pases_confirmados', filter=Q(estado='confirmado')),
            n_rechazados=Count('id', filter=Q(estado='rechazado')),
            n_pendientes=Count('id', filter=Q(estado='pendiente')),
            n_vistos=Count('id', filter=Q(vista_en__isnull=False)),
            n_llegaron=Count('id', filter=Q(check_in_en__isnull=False)),
            suma_llegaron=Sum('pases_confirmados', filter=Q(check_in_en__isnull=False)),
        )
        return {
            'total': datos['n_total'],
            'pases': datos['suma_pases'] or 0,
            'confirmados': datos['n_confirmados'],
            'pases_confirmados': datos['suma_confirmados'] or 0,
            'rechazados': datos['n_rechazados'],
            'pendientes': datos['n_pendientes'],
            'vistos': datos['n_vistos'],
            'llegaron': datos['n_llegaron'],
            'pases_llegaron': datos['suma_llegaron'] or 0,
        }


class Invitado(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        CONFIRMADO = 'confirmado', 'Confirmado'
        RECHAZADO = 'rechazado', 'No asistirá'

    class Origen(models.TextChoices):
        LISTA = 'lista', 'Lista'
        PUBLICO = 'publico', 'Enlace general'

    evento = models.ForeignKey('eventos.Evento', on_delete=models.CASCADE, related_name='invitados')
    nombre = models.CharField(max_length=150, help_text='Persona o familia, p. ej. "Familia Pérez".')
    telefono = models.CharField('WhatsApp', max_length=30, blank=True)
    email = models.EmailField('correo', blank=True)
    pases = models.PositiveSmallIntegerField(default=1)
    grupo = models.CharField(max_length=60, blank=True, help_text='Ej. Familia novia, Amigos, Trabajo.')
    mesa = models.CharField(max_length=30, blank=True)
    notas = models.CharField(max_length=255, blank=True)

    token = models.CharField(max_length=32, unique=True, default=generar_token, editable=False)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    pases_confirmados = models.PositiveSmallIntegerField(default=0)
    mensaje = models.TextField('mensaje del invitado', blank=True)
    origen = models.CharField(max_length=10, choices=Origen.choices, default=Origen.LISTA)

    respondido_en = models.DateTimeField(null=True, blank=True)
    vista_en = models.DateTimeField(null=True, blank=True)
    enviada_en = models.DateTimeField(null=True, blank=True)
    check_in_en = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    objects = InvitadoQuerySet.as_manager()

    class Meta:
        ordering = ['nombre']
        verbose_name = 'invitado'
        verbose_name_plural = 'invitados'

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        invitacion = self.evento.invitacion
        return reverse('invitacion_publica:personal', args=[invitacion.slug, self.token])

    @property
    def whatsapp_numero(self):
        numero = ''.join(c for c in self.telefono if c.isdigit())
        if len(numero) == 10:
            numero = '52' + numero
        return numero
