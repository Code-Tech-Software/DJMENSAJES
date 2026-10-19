from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone

from apps.core.utils import generar_codigo, generar_token


class TipoEvento(models.TextChoices):
    BODA = 'boda', 'Boda'
    QUINCE = 'quinse', 'XV Años'  # la clave conserva la ortografía original por compatibilidad
    CUMPLE = 'cumple', 'Cumpleaños'
    FIESTA = 'fiesta', 'Fiesta'
    BAUTIZO = 'bautizo', 'Bautizo'
    GRADUACION = 'graduacion', 'Graduación'
    CORPORATIVO = 'corporativo', 'Corporativo'
    ANIVERSARIO = 'aniversario', 'Aniversario'
    OTRO = 'otro', 'Otro'


ICONOS_TIPO = {
    'boda': 'ph ph-heart-straight',
    'quinse': 'ph ph-crown-simple',
    'cumple': 'ph ph-cake',
    'fiesta': 'ph ph-vinyl-record',
    'bautizo': 'ph ph-drop',
    'graduacion': 'ph ph-graduation-cap',
    'corporativo': 'ph ph-briefcase',
    'aniversario': 'ph ph-gift',
    'otro': 'ph ph-calendar-dots',
}


def _codigo_unico():
    return generar_codigo(7)


def _token_dj():
    return generar_token(18)


class EventoQuerySet(models.QuerySet):
    def visibles_para(self, usuario):
        """Eventos que el usuario puede consultar: solo de su agencia y, dentro de ella, según su rol."""
        if not usuario.is_authenticated or not usuario.agencia_id:
            return self.none()
        de_su_agencia = self.filter(agencia_id=usuario.agencia_id)
        if usuario.ve_todo:
            return de_su_agencia
        filtro = Q(creado_por=usuario)
        if usuario.colaborador_id:
            filtro |= Q(colaborador_id=usuario.colaborador_id)
        return de_su_agencia.filter(filtro)

    def proximos(self):
        return self.filter(fecha_inicio_evento__gt=timezone.now())

    def en_curso(self):
        ahora = timezone.now()
        return self.filter(fecha_inicio_evento__lte=ahora, fecha_fin_evento__gte=ahora)

    def pasados(self):
        return self.filter(fecha_fin_evento__lt=timezone.now())

    def vigentes(self):
        return self.exclude(etapa=Evento.Etapa.CANCELADO)


class Evento(models.Model):
    class Etapa(models.TextChoices):
        COTIZACION = 'cotizacion', 'Cotización'
        CONFIRMADO = 'confirmado', 'Confirmado'
        CANCELADO = 'cancelado', 'Cancelado'

    class ContenidoPantalla(models.TextChoices):
        TODO = 'todo', 'Mensajes y fotos'
        MENSAJES = 'mensajes', 'Solo mensajes'
        FOTOS = 'fotos', 'Solo fotos'

    class TamanoQR(models.TextChoices):
        GRANDE = 'grande', 'Gigante'
        ESQUINA = 'esquina', 'En una esquina'

    # --- Datos generales
    nombre_evento = models.CharField(
        'nombre del evento', max_length=200,
        help_text='Así se verá en las pantallas, p. ej. "Ana & Luis" o "Sofía".',
    )
    tipo_evento = models.CharField('tipo de evento', max_length=50, choices=TipoEvento.choices)
    etapa = models.CharField(max_length=20, choices=Etapa.choices, default=Etapa.CONFIRMADO)
    agencia = models.ForeignKey('core.Agencia', on_delete=models.PROTECT, related_name='eventos', editable=False)
    colaborador = models.ForeignKey(
        'colaboradores.Colaborador', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eventos', help_text='Sub-agencia que opera el evento.',
    )
    banner = models.ForeignKey(
        'banners.Banner', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eventos', verbose_name='fondo visual',
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eventos',
    )

    # --- Fecha y lugar
    fecha_inicio_evento = models.DateTimeField('inicio')
    fecha_fin_evento = models.DateTimeField('fin')
    lugar = models.CharField('salón / lugar', max_length=150, blank=True)
    direccion = models.CharField('dirección', max_length=255, blank=True)
    url_mapa = models.URLField('enlace de Google Maps', blank=True)
    num_invitados = models.PositiveIntegerField('invitados estimados', null=True, blank=True)

    # --- Cliente y contrato
    cliente_nombre = models.CharField('nombre del cliente', max_length=150, blank=True)
    cliente_telefono = models.CharField('teléfono del cliente', max_length=30, blank=True)
    cliente_email = models.EmailField('correo del cliente', blank=True)
    precio_total = models.DecimalField(
        'precio total', max_digits=12, decimal_places=2, default=Decimal('0'),
    )
    servicios = models.TextField('servicios contratados', blank=True, help_text='Uno por línea.')
    notas = models.TextField('notas internas', blank=True)

    # --- Interacción en vivo
    estado = models.BooleanField(
        'interacción activa', default=True,
        help_text='Permite que los invitados envíen saludos y canciones.',
    )
    codigo = models.CharField(max_length=12, unique=True, default=_codigo_unico, editable=False)
    token_dj = models.CharField(max_length=40, unique=True, default=_token_dj, editable=False)
    password_vip = models.CharField(
        'contraseña VIP', max_length=100, blank=True,
        help_text='Los invitados VIP no tienen tiempo de espera. Déjala vacía para desactivar VIP.',
    )
    cooldown = models.FloatField(
        'tiempo entre mensajes (min)', default=2,
        help_text='Minutos que debe esperar un invitado para enviar otro mensaje.',
    )
    permitir_saludos = models.BooleanField('recibir saludos', default=True)
    permitir_canciones = models.BooleanField('recibir canciones', default=True)
    limite_fotos = models.PositiveIntegerField(
        'límite de fotos', null=True, blank=True,
        help_text='Cuántas fotos pueden subir los invitados. Vacío = lo que permita el plan.',
    )
    permitir_fotos = models.BooleanField(
        'recibir fotos', default=True,
        help_text='Los invitados comparten fotos; el DJ las aprueba para la pantalla y el álbum.',
    )
    moderar_pantalla = models.BooleanField(
        'moderar proyector', default=True,
        help_text='Los saludos aparecen en el proyector solo cuando el DJ los aprueba.',
    )
    pantalla_contenido = models.CharField(
        'qué muestra el proyector', max_length=10, choices=ContenidoPantalla.choices, default=ContenidoPantalla.TODO,
        help_text='Las fotos siempre pasan antes por la aprobación del DJ.',
    )
    pantalla_qr = models.CharField(
        'código QR en el proyector', max_length=10, choices=TamanoQR.choices, default=TamanoQR.GRANDE,
        help_text='Gigante a un lado o pequeño en una esquina para dejarle más espacio a mensajes y fotos.',
    )
    mensaje_bienvenida = models.CharField(
        'mensaje de bienvenida', max_length=255, blank=True,
        help_text='Texto que verán los invitados al escanear el QR.',
    )

    creado = models.DateTimeField(default=timezone.now, editable=False)
    actualizado = models.DateTimeField(auto_now=True)

    objects = EventoQuerySet.as_manager()

    class Meta:
        ordering = ['-fecha_inicio_evento']
        verbose_name = 'evento'
        verbose_name_plural = 'eventos'
        indexes = [models.Index(fields=['fecha_inicio_evento'])]

    def __str__(self):
        return self.nombre_evento

    def get_absolute_url(self):
        return reverse('eventos:detalle', args=[self.pk])

    # --- Presentación
    @property
    def icono(self):
        return ICONOS_TIPO.get(self.tipo_evento, ICONOS_TIPO['otro'])

    @property
    def tipo_corto(self):
        return 'XV Años' if self.tipo_evento == TipoEvento.QUINCE else self.get_tipo_evento_display()

    @property
    def estado_temporal(self):
        ahora = timezone.now()
        if self.etapa == self.Etapa.CANCELADO:
            return 'cancelado'
        if self.fecha_fin_evento < ahora:
            return 'finalizado'
        if self.fecha_inicio_evento <= ahora:
            return 'en_curso'
        return 'proximo'

    @property
    def estado_temporal_display(self):
        return {
            'cancelado': 'Cancelado',
            'finalizado': 'Finalizado',
            'en_curso': 'En curso',
            'proximo': 'Próximo',
        }[self.estado_temporal]

    @property
    def dias_restantes(self):
        return (timezone.localdate(self.fecha_inicio_evento) - timezone.localdate()).days

    @property
    def duracion_horas(self):
        return round((self.fecha_fin_evento - self.fecha_inicio_evento).total_seconds() / 3600, 1)

    @property
    def lista_servicios(self):
        return [s.strip(' -•\t') for s in self.servicios.splitlines() if s.strip(' -•\t')]

    # --- Finanzas
    @property
    def total_pagado(self):
        if hasattr(self, '_total_pagado'):
            return self._total_pagado
        self._total_pagado = self.pagos.aggregate(t=Sum('monto'))['t'] or Decimal('0')
        return self._total_pagado

    @property
    def saldo(self):
        return max(self.precio_total - self.total_pagado, Decimal('0'))

    @property
    def porcentaje_pagado(self):
        if not self.precio_total:
            return 0
        return min(100, int(self.total_pagado * 100 / self.precio_total))

    # --- Enlaces públicos
    def url_invitados(self):
        return reverse('envivo:invitado', args=[self.codigo])

    def url_pantalla(self):
        return reverse('envivo:pantalla', args=[self.codigo])

    def url_dj(self):
        return reverse('envivo:dj', args=[self.token_dj])

    def url_album(self):
        return reverse('envivo:album', args=[self.codigo])

    def url_pantalla_fotos(self):
        return reverse('envivo:pantalla_fotos', args=[self.codigo])

    def imagen_portada(self):
        invitacion = getattr(self, 'invitacion', None)
        if invitacion and invitacion.portada:
            return invitacion.portada
        if self.banner_id:
            return self.banner.imagen_portada
        return None


class ActividadItinerario(models.Model):
    class Icono(models.TextChoices):
        CEREMONIA = 'ceremonia', 'Ceremonia'
        RECEPCION = 'recepcion', 'Recepción'
        CENA = 'cena', 'Cena'
        BRINDIS = 'brindis', 'Brindis'
        VALS = 'vals', 'Vals / Baile'
        FOTOS = 'fotos', 'Fotos'
        FIESTA = 'fiesta', 'Fiesta'
        PASTEL = 'pastel', 'Pastel'
        OTRO = 'otro', 'Otro'

    ICONOS = {
        'ceremonia': 'ph ph-church',
        'recepcion': 'ph ph-door-open',
        'cena': 'ph ph-fork-knife',
        'brindis': 'ph ph-wine',
        'vals': 'ph ph-music-notes',
        'fotos': 'ph ph-camera',
        'fiesta': 'ph ph-vinyl-record',
        'pastel': 'ph ph-cake',
        'otro': 'ph ph-star',
    }

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='itinerario')
    hora = models.TimeField()
    titulo = models.CharField('actividad', max_length=120)
    descripcion = models.CharField('descripción', max_length=255, blank=True)
    icono = models.CharField(max_length=20, choices=Icono.choices, default=Icono.OTRO)

    class Meta:
        ordering = ['hora', 'id']
        verbose_name = 'actividad del itinerario'
        verbose_name_plural = 'itinerario'

    def __str__(self):
        return f'{self.hora:%H:%M} · {self.titulo}'

    @property
    def clase_icono(self):
        return self.ICONOS.get(self.icono, self.ICONOS['otro'])


class Pago(models.Model):
    class Metodo(models.TextChoices):
        EFECTIVO = 'efectivo', 'Efectivo'
        TRANSFERENCIA = 'transferencia', 'Transferencia'
        TARJETA = 'tarjeta', 'Tarjeta'
        OTRO = 'otro', 'Otro'

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='pagos')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateField(default=timezone.localdate)
    metodo = models.CharField('método', max_length=20, choices=Metodo.choices, default=Metodo.TRANSFERENCIA)
    referencia = models.CharField('referencia / nota', max_length=150, blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
        verbose_name = 'pago'
        verbose_name_plural = 'pagos'

    def __str__(self):
        return f'${self.monto} · {self.evento}'
