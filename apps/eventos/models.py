from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
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

    # --- Experiencia en vivo: un extra del evento (se activa a mano o al vender un servicio que la activa)
    con_en_vivo = models.BooleanField(
        'experiencia en vivo', default=False,
        help_text='Pantalla de invitados con QR, canciones, saludos y fotos, proyector y panel del DJ.',
    )
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

    def itinerario_en_orden(self):
        """Actividades en el orden de la fiesta: las de la madrugada (antes de las 8:00) van después de las de la noche."""
        inicio = timezone.localtime(self.fecha_inicio_evento).time()
        return sorted(self.itinerario.all(), key=lambda a: (a.hora < inicio and a.hora.hour < 8, a.hora, a.pk))

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


# --- Cotizaciones ---------------------------------------------------------------------------------
# Cada agencia arma su catálogo (servicios con precio y paquetes), cotiza en un minuto, comparte el PDF o
# un enlace, y cuando el cliente acepta la cotización se convierte en evento.

class CategoriaServicio(models.TextChoices):
    DIGITAL = 'digital', 'Servicios digitales'
    AUDIO = 'audio', 'Audio'
    ILUMINACION = 'iluminacion', 'Iluminación'
    PISTA = 'pista', 'Pista y escenario'
    PANTALLAS = 'pantallas', 'Pantallas y video'
    EFECTOS = 'efectos', 'Efectos especiales'
    FOTO = 'foto', 'Foto y cabina'
    ANIMACION = 'animacion', 'Animación'
    PERSONAL = 'personal', 'DJ y personal'
    EXTRA = 'extra', 'Horas extra'
    OTRO = 'otro', 'Otro'


# Orden en que se muestran (lo primero que se cotiza, arriba); la base no lo garantiza por sí sola
ORDEN_CATEGORIAS = ['personal', 'digital', 'audio', 'iluminacion', 'pista', 'pantallas', 'efectos', 'foto', 'animacion', 'extra', 'otro']


def orden_servicio(servicio):
    categoria = servicio.categoria if hasattr(servicio, 'categoria') else servicio['categoria']
    return (ORDEN_CATEGORIAS.index(categoria) if categoria in ORDEN_CATEGORIAS else 99,)


ICONOS_CATEGORIA = {
    'digital': 'ph ph-device-mobile',
    'audio': 'ph ph-speaker-hifi',
    'iluminacion': 'ph ph-lightbulb-filament',
    'pista': 'ph ph-squares-four',
    'pantallas': 'ph ph-monitor-play',
    'efectos': 'ph ph-sparkle',
    'foto': 'ph ph-camera',
    'animacion': 'ph ph-confetti',
    'personal': 'ph ph-headphones',
    'extra': 'ph ph-clock-clockwise',
    'otro': 'ph ph-tag',
}


class Servicio(models.Model):
    """Lo que la agencia cobra: audio, iluminación, pista, cabina, hora extra…"""

    class Unidad(models.TextChoices):
        EVENTO = 'evento', 'por evento'
        HORA = 'hora', 'por hora'
        PIEZA = 'pieza', 'por pieza'
        PERSONA = 'persona', 'por persona'

    class Activa(models.TextChoices):
        NADA = '', 'Nada'
        EN_VIVO = 'en_vivo', 'Experiencia en vivo'
        INVITACION = 'invitacion', 'Invitación digital'

    agencia = models.ForeignKey('core.Agencia', on_delete=models.CASCADE, related_name='servicios', editable=False)
    nombre = models.CharField(max_length=120)
    descripcion = models.CharField('descripción', max_length=255, blank=True, help_text='Lo que incluye; sale en la cotización.')
    categoria = models.CharField('categoría', max_length=20, choices=CategoriaServicio.choices, default=CategoriaServicio.OTRO)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    unidad = models.CharField(max_length=10, choices=Unidad.choices, default=Unidad.EVENTO)
    activa = models.CharField(
        'al venderlo activa', max_length=12, choices=Activa.choices, default=Activa.NADA, blank=True,
        help_text='Si un evento lo incluye (o se acepta una cotización con él), ese extra se activa solo.',
    )
    activo = models.BooleanField(default=True, help_text='Los inactivos ya no aparecen al cotizar.')
    orden = models.PositiveSmallIntegerField(default=0)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['categoria', 'orden', 'nombre']
        verbose_name = 'servicio del catálogo'
        verbose_name_plural = 'catálogo de servicios'

    def __str__(self):
        return self.nombre

    @property
    def icono(self):
        return ICONOS_CATEGORIA.get(self.categoria, ICONOS_CATEGORIA['otro'])


class Paquete(models.Model):
    """Varios servicios juntos con un precio especial (p. ej. "Boda Plata")."""

    agencia = models.ForeignKey('core.Agencia', on_delete=models.CASCADE, related_name='paquetes', editable=False)
    nombre = models.CharField(max_length=120)
    descripcion = models.CharField('descripción', max_length=255, blank=True)
    precio = models.DecimalField('precio del paquete', max_digits=12, decimal_places=2)
    servicios = models.ManyToManyField(Servicio, through='PaqueteServicio', related_name='paquetes')
    activo = models.BooleanField(default=True, help_text='Los inactivos ya no aparecen al cotizar.')
    orden = models.PositiveSmallIntegerField(default=0)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['orden', 'precio', 'nombre']
        verbose_name = 'paquete'
        verbose_name_plural = 'paquetes'

    def __str__(self):
        return self.nombre

    @property
    def precio_por_separado(self):
        return sum((i.servicio.precio * i.cantidad for i in self.items.all()), Decimal('0'))

    @property
    def ahorro(self):
        return max(self.precio_por_separado - self.precio, Decimal('0'))

    @property
    def detalle(self):
        """'Audio profesional, Iluminación, 2 h de hora extra…' para la cotización."""
        return ', '.join(i.texto for i in self.items.all())


class PaqueteServicio(models.Model):
    paquete = models.ForeignKey(Paquete, on_delete=models.CASCADE, related_name='items')
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name='+')
    cantidad = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('1'))

    class Meta:
        ordering = ['id']
        unique_together = [('paquete', 'servicio')]
        verbose_name = 'servicio del paquete'
        verbose_name_plural = 'servicios del paquete'

    @property
    def texto(self):
        if self.cantidad == 1:
            return self.servicio.nombre
        cantidad = f'{self.cantidad.normalize():f}'
        return f'{cantidad} h de {self.servicio.nombre.lower()}' if self.servicio.unidad == Servicio.Unidad.HORA \
            else f'{cantidad} × {self.servicio.nombre}'


def _token_cotizacion():
    return generar_token(18)


class CotizacionQuerySet(models.QuerySet):
    def visibles_para(self, usuario):
        """Igual que los eventos: solo de su agencia y, dentro de ella, según su rol."""
        if not usuario.is_authenticated or not usuario.agencia_id:
            return self.none()
        de_su_agencia = self.filter(agencia_id=usuario.agencia_id)
        if usuario.ve_todo:
            return de_su_agencia
        filtro = Q(creado_por=usuario)
        if usuario.colaborador_id:
            filtro |= Q(colaborador_id=usuario.colaborador_id)
        return de_su_agencia.filter(filtro)


class Cotizacion(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'borrador', 'Borrador'
        ENVIADA = 'enviada', 'Enviada'
        ACEPTADA = 'aceptada', 'Aceptada'
        RECHAZADA = 'rechazada', 'Rechazada'

    TONOS = {'borrador': 'muted', 'enviada': 'info', 'aceptada': 'success', 'rechazada': 'danger', 'vencida': 'warning'}

    agencia = models.ForeignKey('core.Agencia', on_delete=models.PROTECT, related_name='cotizaciones', editable=False)
    numero = models.PositiveIntegerField(editable=False)
    token = models.CharField(max_length=40, unique=True, default=_token_cotizacion, editable=False)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.BORRADOR)
    colaborador = models.ForeignKey(
        'colaboradores.Colaborador', on_delete=models.SET_NULL, null=True, blank=True, related_name='cotizaciones',
        help_text='Sub-agencia que la ofrece.',
    )
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    # Cliente
    cliente_nombre = models.CharField('cliente', max_length=150)
    cliente_telefono = models.CharField('teléfono', max_length=30, blank=True)
    cliente_email = models.EmailField('correo', blank=True)

    # Evento que se cotiza
    nombre_evento = models.CharField('nombre del evento', max_length=200, blank=True, help_text='Vacío = el nombre del cliente.')
    tipo_evento = models.CharField('tipo de evento', max_length=50, choices=TipoEvento.choices, default=TipoEvento.BODA)
    fecha_evento = models.DateTimeField('fecha y hora')
    duracion_horas = models.DecimalField('duración (horas)', max_digits=4, decimal_places=1, default=Decimal('5'))
    lugar = models.CharField('salón / lugar', max_length=150, blank=True)
    num_invitados = models.PositiveIntegerField('invitados', null=True, blank=True)

    # Importes y condiciones
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    anticipo_porcentaje = models.PositiveSmallIntegerField(
        'anticipo para apartar (%)', default=30, validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    vigencia = models.DateField('válida hasta')
    condiciones = models.TextField('condiciones', blank=True, help_text='Las ve el cliente en la cotización.')
    notas_internas = models.TextField('notas internas', blank=True)

    # Seguimiento
    evento = models.OneToOneField(Evento, on_delete=models.SET_NULL, null=True, blank=True, related_name='cotizacion')
    enviada_el = models.DateTimeField(null=True, blank=True, editable=False)
    vista_el = models.DateTimeField(null=True, blank=True, editable=False, help_text='Primera vez que el cliente la abrió.')
    respondida_el = models.DateTimeField(null=True, blank=True, editable=False)
    aceptada_por = models.CharField(max_length=150, blank=True, editable=False)
    creado = models.DateTimeField(default=timezone.now, editable=False)
    actualizado = models.DateTimeField(auto_now=True)

    objects = CotizacionQuerySet.as_manager()

    class Meta:
        ordering = ['-creado']
        unique_together = [('agencia', 'numero')]
        verbose_name = 'cotización'
        verbose_name_plural = 'cotizaciones'

    def __str__(self):
        return f'{self.folio} · {self.cliente_nombre}'

    def save(self, *args, **kwargs):
        if not self.numero:  # folio consecutivo por agencia
            ultimo = Cotizacion.objects.filter(agencia_id=self.agencia_id).aggregate(n=models.Max('numero'))['n']
            self.numero = (ultimo or 0) + 1
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('cotizaciones:detalle', args=[self.pk])

    def url_cliente(self):
        return reverse('cotizacion_publica', args=[self.token])

    @property
    def folio(self):
        return f'COT-{self.numero:04d}'

    @property
    def titulo_evento(self):
        return self.nombre_evento or self.cliente_nombre

    @property
    def fecha_fin(self):
        return self.fecha_evento + timedelta(hours=float(self.duracion_horas))

    @property
    def subtotal(self):
        if not hasattr(self, '_subtotal'):
            self._subtotal = sum((c.importe for c in self.conceptos.all()), Decimal('0'))
        return self._subtotal

    @property
    def total(self):
        return max(self.subtotal - self.descuento, Decimal('0'))

    @property
    def anticipo(self):
        return (self.total * self.anticipo_porcentaje / 100).quantize(Decimal('0.01'))

    @property
    def vencida(self):
        return self.estado in (self.Estado.BORRADOR, self.Estado.ENVIADA) and self.vigencia < timezone.localdate()

    @property
    def abierta(self):
        """El cliente todavía la puede aceptar."""
        return self.estado in (self.Estado.BORRADOR, self.Estado.ENVIADA) and not self.vencida

    @property
    def estado_clave(self):
        return 'vencida' if self.vencida else self.estado

    @property
    def estado_visible(self):
        return 'Vencida' if self.vencida else self.get_estado_display()

    @property
    def tono(self):
        return self.TONOS[self.estado_clave]


class ConceptoBase(models.Model):
    """Un renglón con precio: un servicio o paquete del catálogo, o algo escrito a mano."""

    servicio = models.ForeignKey(Servicio, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    paquete = models.ForeignKey(Paquete, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    descripcion = models.CharField('concepto', max_length=160)
    detalle = models.CharField(max_length=400, blank=True)
    cantidad = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('1'))
    unidad = models.CharField(max_length=10, blank=True)
    precio_unitario = models.DecimalField('precio', max_digits=12, decimal_places=2)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ['orden', 'id']

    def __str__(self):
        return self.descripcion

    @property
    def importe(self):
        return (self.cantidad * self.precio_unitario).quantize(Decimal('0.01'))

    @property
    def texto_servicio(self):
        """Cómo se lee en "servicios contratados" (orden de servicio): con el detalle del paquete y la cantidad."""
        texto = f'{self.descripcion}: {self.detalle}' if self.paquete_id and self.detalle else self.descripcion
        if self.cantidad == 1:
            return texto
        cantidad = f'{self.cantidad.normalize():f}'
        return f'{texto} ({cantidad} h)' if self.unidad == Servicio.Unidad.HORA else f'{texto} (× {cantidad})'


class ConceptoCotizacion(ConceptoBase):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='conceptos')

    class Meta(ConceptoBase.Meta):
        verbose_name = 'concepto'
        verbose_name_plural = 'conceptos'


class ConceptoEvento(ConceptoBase):
    """Servicios contratados del evento con su precio (del catálogo o de su cotización)."""

    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='conceptos')

    class Meta(ConceptoBase.Meta):
        verbose_name = 'servicio contratado'
        verbose_name_plural = 'servicios contratados'
