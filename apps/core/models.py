from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import DatabaseError, models


class Ajustes(models.Model):
    """Ajustes generales de la plataforma (un solo registro).

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

    # Marca y contacto
    nombre = models.CharField('nombre del negocio', max_length=80, default='Grupo EM')
    eslogan = models.CharField(max_length=120, blank=True, default='Hacemos vibrar tu fiesta')
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
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CLAVE_CACHE)

    def delete(self, *args, **kwargs):
        cache.delete(self.CLAVE_CACHE)
        return super().delete(*args, **kwargs)

    @classmethod
    def cargar(cls):
        """El registro de ajustes (se crea con los valores de fábrica la primera vez)."""
        ajustes = cache.get(cls.CLAVE_CACHE)
        if ajustes is None:
            try:
                ajustes, _ = cls.objects.get_or_create(pk=1)
            except DatabaseError:
                return cls()  # aún no se corre migrate: valores de fábrica sin guardar
            cache.set(cls.CLAVE_CACHE, ajustes, 300)
        return ajustes

    @property
    def whatsapp_url(self):
        numero = ''.join(c for c in self.whatsapp if c.isdigit())
        if len(numero) == 10:  # número mexicano sin lada internacional
            numero = '52' + numero
        return f'https://wa.me/{numero}' if numero else ''

    @property
    def tiene_contacto(self):
        return bool(self.whatsapp_url or self.instagram or self.facebook or self.tiktok or self.sitio_web)
