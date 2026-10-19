from django.conf import settings
from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import DatabaseError, models
from django.utils import timezone


class Plan(models.Model):
    """Lo que EventPro le renta a una agencia: precio de referencia y límites (vacío = sin límite)."""

    nombre = models.CharField(max_length=60, unique=True)
    precio_mensual = models.DecimalField('precio mensual', max_digits=10, decimal_places=2, default=0)
    max_eventos_mes = models.PositiveIntegerField('eventos al mes', null=True, blank=True, help_text='Vacío = sin límite.')
    max_usuarios = models.PositiveIntegerField('usuarios activos', null=True, blank=True, help_text='Vacío = sin límite.')
    max_colaboradores = models.PositiveIntegerField('sub-agencias', null=True, blank=True, help_text='Vacío = sin límite. 0 = sin sección de sub-agencias.')
    max_fotos_mes = models.PositiveIntegerField(
        'bolsa de fotos al mes', null=True, blank=True,
        help_text='Fotos de invitados al mes para todos los eventos de la agencia; en cada evento se aparta una parte. '
                  'Vacío = sin límite.',
    )

    # Módulos: qué secciones y opciones incluye (lo básico —calendario, eventos, pagos y orden de servicio— siempre)
    con_invitaciones = models.BooleanField(
        'invitaciones digitales', default=True,
        help_text='Diseño de la invitación, lista de invitados, confirmaciones, enlace de anfitriones y entrada con QR.',
    )
    con_en_vivo = models.BooleanField(
        'experiencia en vivo', default=True,
        help_text='Pantalla de invitados con QR, canciones y saludos, proyector y panel del DJ.',
    )
    con_fotos = models.BooleanField('fotos de invitados', default=True, help_text='Los invitados suben fotos al evento (requiere experiencia en vivo).')
    con_album = models.BooleanField('álbum digital', default=True, help_text='Álbum en línea con las fotos y saludos del evento (requiere experiencia en vivo).')
    con_banners = models.BooleanField(
        'banners propios', default=True,
        help_text='Subir sus propios fondos. Sin esto solo usan los de la biblioteca de EventPro.',
    )
    descripcion = models.CharField('descripción', max_length=200, blank=True)
    activo = models.BooleanField(default=True, help_text='Los planes inactivos ya no se ofrecen a agencias nuevas.')
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'precio_mensual', 'nombre']
        verbose_name = 'plan'
        verbose_name_plural = 'planes'

    def __str__(self):
        return self.nombre


class Agencia(models.Model):
    """
    Cliente de EventPro: una agencia, DJ o negocio de eventos que renta la plataforma.
    Todo lo que administra (equipo, sub-agencias, banners y eventos) le pertenece y
    tiene sus propios Ajustes (marca, contacto y valores por defecto).
    """

    DIAS_AVISO = 7  # días antes del vencimiento en que se avisa a la agencia

    ESTADOS = {
        'activa': ('Activa', 'success'),
        'por_vencer': ('Vence pronto', 'warning'),
        'vencida': ('Vencida', 'danger'),
        'suspendida': ('Suspendida', 'muted'),
    }

    nombre = models.CharField(max_length=120)
    slug = models.SlugField(max_length=60, unique=True)
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, null=True, blank=True, related_name='agencias',
        help_text='Define sus límites y el precio de referencia. Vacío = sin límites.',
    )
    activa = models.BooleanField(default=True, help_text='Desactívala para suspender su acceso.')
    vence_el = models.DateField('vence el', null=True, blank=True, help_text='Vacío = sin vencimiento.')
    notas = models.TextField(blank=True, help_text='Solo para EventPro: plan acordado, contacto de cobro, etc.')
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'agencia'
        verbose_name_plural = 'agencias'

    def __str__(self):
        return self.nombre

    @property
    def vigente(self):
        return self.activa and (self.vence_el is None or self.vence_el >= timezone.localdate())

    @property
    def dias_restantes(self):
        """Días hasta el vencimiento (negativo si ya venció); None si no vence."""
        return (self.vence_el - timezone.localdate()).days if self.vence_el else None

    @property
    def estado(self):
        if not self.activa:
            return 'suspendida'
        dias = self.dias_restantes
        if dias is not None and dias < 0:
            return 'vencida'
        if dias is not None and dias <= self.DIAS_AVISO:
            return 'por_vencer'
        return 'activa'

    @property
    def estado_visible(self):
        return self.ESTADOS[self.estado][0]

    @property
    def estado_tono(self):
        return self.ESTADOS[self.estado][1]


class Ajustes(models.Model):
    """Ajustes de una agencia (uno por agencia).

    Marca y contacto del negocio (se muestran cuando un evento no tiene sub-agencia)
    y los valores con los que nacen los eventos e invitaciones nuevos.
    """

    CLAVE_CACHE = 'core:ajustes'

    class Plantilla(models.TextChoices):
        AUTOMATICA = '', 'Según el tipo de evento'
        ELEGANTE = 'elegante', 'Elegante'
        JARDIN = 'jardin', 'Jardín'
        MODERNA = 'moderna', 'Moderna'
        FIESTA = 'fiesta', 'Neón'

    agencia = models.OneToOneField(
        Agencia, on_delete=models.CASCADE, null=True, blank=True, related_name='ajustes', editable=False,
    )

    # Marca y contacto
    nombre = models.CharField('nombre del negocio', max_length=80, default='EventPro')
    eslogan = models.CharField(max_length=120, blank=True, default='Hacemos vibrar tu fiesta')
    # Igual que en las sub-agencias: logos pensados para fondo oscuro (pantallas, pie de la invitación)
    logo_principal = models.ImageField(
        'logo', upload_to='agencias/', blank=True, null=True,
        help_text='Para el proyector, la invitación, el álbum y la orden de servicio. Mejor en PNG con fondo transparente.',
    )
    logo_secundario = models.ImageField(
        'logo para el pie', upload_to='agencias/', blank=True, null=True,
        help_text='Opcional: versión para el pie de la pantalla de invitados (fondo oscuro).',
    )
    color_marca = models.CharField(
        'color de marca', max_length=7, default='#0098DA',
        help_text='Acento de las pantallas de invitados, el proyector y el álbum.',
    )
    whatsapp = models.CharField(
        'WhatsApp', max_length=20, blank=True, help_text='10 dígitos (México) o con código de país.',
    )
    telefono = models.CharField('teléfono', max_length=30, blank=True)
    email = models.EmailField('correo', blank=True)
    sitio_web = models.URLField('sitio web', blank=True)
    instagram = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    tiktok = models.URLField('TikTok', blank=True)

    # Valores para eventos nuevos
    cooldown = models.FloatField(
        'tiempo entre mensajes (min)', default=2,
        validators=[MinValueValidator(0), MaxValueValidator(60)],
        help_text='Minutos que espera un invitado para mandar otro mensaje.',
    )
    permitir_saludos = models.BooleanField('recibir saludos', default=True)
    permitir_canciones = models.BooleanField('recibir canciones', default=True)
    permitir_fotos = models.BooleanField('recibir fotos', default=True)
    moderar_pantalla = models.BooleanField(
        'moderar proyector', default=True,
        help_text='Los saludos salen en el proyector solo cuando el DJ los aprueba.',
    )
    mensaje_bienvenida = models.CharField(
        'mensaje de bienvenida', max_length=255, blank=True,
        help_text='Lo ven los invitados al escanear el QR.',
    )

    # Invitaciones nuevas
    plantilla = models.CharField(
        'plantilla inicial', max_length=20, choices=Plantilla.choices, blank=True, default=Plantilla.AUTOMATICA,
    )
    dias_limite_rsvp = models.PositiveSmallIntegerField(
        'cerrar confirmaciones', default=7, validators=[MaxValueValidator(90)],
        help_text='Días antes del evento.',
    )

    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'ajustes'
        verbose_name_plural = 'ajustes'

    def __str__(self):
        return f'Ajustes de {self.nombre}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(self.clave_cache(self.agencia_id))

    def delete(self, *args, **kwargs):
        cache.delete(self.clave_cache(self.agencia_id))
        return super().delete(*args, **kwargs)

    @classmethod
    def plataforma(cls):
        """Datos de contacto de EventPro (el registro sin agencia): las agencias los ven para renovar."""
        try:
            return cls.objects.filter(agencia__isnull=True).order_by('pk').first() or cls.objects.create(nombre='EventPro', eslogan='')
        except DatabaseError:
            return cls()

    @classmethod
    def clave_cache(cls, agencia_id):
        return f'{cls.CLAVE_CACHE}:{agencia_id}'

    @classmethod
    def de(cls, agencia):
        """
        Los ajustes de una agencia (objeto o id); se crean con los valores de fábrica la primera vez.
        Sin agencia (inicio de sesión, cuentas de EventPro) se usan los de fábrica sin guardar.
        """
        agencia_id = getattr(agencia, 'pk', agencia)
        if not agencia_id:
            return cls()
        clave = cls.clave_cache(agencia_id)
        ajustes = cache.get(clave)
        if ajustes is None:
            try:
                ajustes = cls.objects.filter(agencia_id=agencia_id).first()
                if ajustes is None:
                    nombre = getattr(agencia, 'nombre', None) or Agencia.objects.get(pk=agencia_id).nombre
                    ajustes = cls.objects.create(agencia_id=agencia_id, nombre=nombre[:80])
            except DatabaseError:
                return cls()  # aún no se corre migrate: valores de fábrica sin guardar
            cache.set(clave, ajustes, 300)
        return ajustes

    @property
    def whatsapp_url(self):
        numero = ''.join(c for c in self.whatsapp if c.isdigit())
        if len(numero) == 10:  # número mexicano sin lada internacional
            numero = '52' + numero
        return f'https://wa.me/{numero}' if numero else ''

    @property
    def logo(self):
        return self.logo_principal or self.logo_secundario

    @property
    def logo_pie(self):
        return self.logo_secundario or self.logo_principal

    @property
    def tiene_contacto(self):
        return bool(self.whatsapp_url or self.instagram or self.facebook or self.tiktok or self.sitio_web)


class PagoAgencia(models.Model):
    """Un pago que hizo una agencia a EventPro. Registrarlo extiende su vencimiento."""

    class Metodo(models.TextChoices):
        TRANSFERENCIA = 'transferencia', 'Transferencia'
        EFECTIVO = 'efectivo', 'Efectivo'
        TARJETA = 'tarjeta', 'Tarjeta'
        DEPOSITO = 'deposito', 'Depósito'
        OTRO = 'otro', 'Otro'

    agencia = models.ForeignKey(Agencia, on_delete=models.CASCADE, related_name='pagos')
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateField(default=timezone.localdate)
    meses = models.PositiveSmallIntegerField('meses que cubre', default=1)
    metodo = models.CharField('método', max_length=20, choices=Metodo.choices, default=Metodo.TRANSFERENCIA)
    referencia = models.CharField(max_length=120, blank=True, help_text='Folio, banco o una nota.')
    cubre_hasta = models.DateField('cubre hasta', null=True, blank=True, editable=False)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-pk']
        verbose_name = 'pago de agencia'
        verbose_name_plural = 'pagos de agencias'

    def __str__(self):
        return f'{self.agencia} · ${self.monto} · {self.fecha}'


class Bitacora(models.Model):
    """Lo que pasa en la plataforma: quién hizo qué, en qué agencia y cuándo."""

    class Accion(models.TextChoices):
        AGENCIA_CREADA = 'agencia_creada', 'Agencia creada'
        AGENCIA_EDITADA = 'agencia_editada', 'Agencia editada'
        AGENCIA_SUSPENDIDA = 'agencia_suspendida', 'Agencia suspendida'
        AGENCIA_REACTIVADA = 'agencia_reactivada', 'Agencia reactivada'
        VIGENCIA = 'vigencia', 'Vigencia extendida'
        PAGO = 'pago', 'Pago registrado'
        PAGO_ELIMINADO = 'pago_eliminado', 'Pago eliminado'
        PLAN = 'plan', 'Plan modificado'
        USUARIO_CREADO = 'usuario_creado', 'Usuario creado'
        USUARIO_EDITADO = 'usuario_editado', 'Usuario editado'
        USUARIO_ACTIVADO = 'usuario_activado', 'Usuario activado'
        USUARIO_DESACTIVADO = 'usuario_desactivado', 'Usuario desactivado'
        CLAVE = 'clave', 'Contraseña restablecida'
        ENTRAR_COMO = 'entrar_como', 'Entró como otro usuario'
        SALIR_DE = 'salir_de', 'Regresó a su cuenta'
        INICIO_SESION = 'inicio_sesion', 'Inicio de sesión'
        EVENTO_CREADO = 'evento_creado', 'Evento creado'
        LIMITE = 'limite', 'Límite del plan alcanzado'

    ICONOS = {
        'agencia_creada': ('ph ph-buildings', 'tone-success'), 'agencia_editada': ('ph ph-pencil-simple', ''),
        'agencia_suspendida': ('ph ph-prohibit', 'tone-danger'), 'agencia_reactivada': ('ph ph-check-circle', 'tone-success'),
        'vigencia': ('ph ph-calendar-plus', ''), 'pago': ('ph ph-currency-dollar', 'tone-success'),
        'pago_eliminado': ('ph ph-trash', 'tone-danger'), 'plan': ('ph ph-stack', ''),
        'usuario_creado': ('ph ph-user-plus', 'tone-success'), 'usuario_editado': ('ph ph-user-gear', ''),
        'usuario_activado': ('ph ph-user-check', 'tone-success'), 'usuario_desactivado': ('ph ph-user-minus', 'tone-danger'),
        'clave': ('ph ph-key', 'tone-warning'), 'entrar_como': ('ph ph-mask-happy', 'tone-live'), 'salir_de': ('ph ph-arrow-u-up-left', 'tone-live'),
        'inicio_sesion': ('ph ph-sign-in', ''), 'evento_creado': ('ph ph-sparkle', 'tone-info'), 'limite': ('ph ph-gauge', 'tone-warning'),
    }

    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    accion = models.CharField(max_length=30, choices=Accion.choices, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    agencia = models.ForeignKey(Agencia, on_delete=models.SET_NULL, null=True, blank=True, related_name='bitacora')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
                                help_text='Usuario afectado, si aplica.')
    detalle = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha', '-pk']
        verbose_name = 'registro de actividad'
        verbose_name_plural = 'bitácora'

    def __str__(self):
        return f'{self.get_accion_display()} · {self.fecha:%d/%m/%Y %H:%M}'

    @property
    def icono(self):
        return self.ICONOS.get(self.accion, ('ph ph-dot', ''))[0]

    @property
    def tono(self):
        return self.ICONOS.get(self.accion, ('', ''))[1]
