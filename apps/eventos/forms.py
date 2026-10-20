import json
from datetime import datetime, time, timedelta
from decimal import Decimal

from django import forms
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.banners.models import Banner
from apps.colaboradores.models import Colaborador
from apps.core.models import Ajustes
from apps.core.modulos import bolsa_de, bolsa_del_mes, fotos_subidas, modulos_de

from .asistente import DURACIONES, ETAPAS, ITINERARIOS, TEXTOS_TIPO, sugerencias
from .cotizacion.forms import conceptos_json, datos_catalogo, leer_conceptos
from .extras import tiene_invitacion
from .models import ActividadItinerario, ConceptoEvento, Evento, Paquete, Pago, Servicio, TipoEvento

FORMATO_FECHA_HORA = '%Y-%m-%dT%H:%M'


def _fecha_hora(attrs=None):
    return forms.DateTimeInput(attrs={'type': 'datetime-local', **(attrs or {})}, format=FORMATO_FECHA_HORA)


class EventoForm(forms.ModelForm):
    """El evento: qué, cuándo, dónde, para quién y por cuánto. Sus extras (experiencia en vivo, invitación) van aparte."""
    # Solo al crear: el anticipo se registra como primer pago y el itinerario base según el tipo de evento
    anticipo = forms.DecimalField(label='Anticipo recibido', required=False, min_value=0, max_digits=12, decimal_places=2,
                                  widget=forms.NumberInput(attrs={'min': 0, 'step': '0.01', 'placeholder': '0.00'}))
    anticipo_metodo = forms.ChoiceField(label='Cómo pagó', choices=Pago.Metodo.choices, initial=Pago.Metodo.TRANSFERENCIA,
                                        required=False, widget=forms.RadioSelect)
    itinerario_base = forms.BooleanField(label='Agregar el itinerario sugerido', required=False,
                                         help_text='Lo puedes ajustar después en la pestaña Itinerario.')
    # Servicios contratados con precio (del catálogo o a mano); si llegan, "servicios" se arma con ellos
    conceptos = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Evento
        fields = [
            'nombre_evento', 'tipo_evento', 'etapa', 'colaborador',
            'fecha_inicio_evento', 'fecha_fin_evento', 'lugar', 'direccion', 'url_mapa', 'num_invitados',
            'cliente_nombre', 'cliente_telefono', 'cliente_email', 'precio_total', 'servicios', 'notas',
        ]
        widgets = {
            'nombre_evento': forms.TextInput(attrs={'placeholder': 'Ej. Ana & Luis', 'maxlength': 200}),
            'tipo_evento': forms.RadioSelect,
            'etapa': forms.RadioSelect,
            'fecha_inicio_evento': _fecha_hora(),
            'fecha_fin_evento': _fecha_hora(),
            'lugar': forms.TextInput(attrs={'placeholder': 'Ej. Jardín Las Palmas'}),
            'direccion': forms.TextInput(attrs={'placeholder': 'Calle, número, colonia, ciudad'}),
            'url_mapa': forms.URLInput(attrs={'placeholder': 'https://maps.app.goo.gl/…'}),
            'num_invitados': forms.NumberInput(attrs={'min': 0, 'placeholder': 'Ej. 250'}),
            'cliente_nombre': forms.TextInput(attrs={'placeholder': 'Quién contrata'}),
            'cliente_telefono': forms.TextInput(attrs={'placeholder': '10 dígitos', 'inputmode': 'tel'}),
            'cliente_email': forms.EmailInput(attrs={'placeholder': 'cliente@correo.com'}),
            'precio_total': forms.NumberInput(attrs={'min': 0, 'step': '0.01', 'placeholder': '0.00'}),
            'servicios': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Audio e iluminación\nDJ 6 horas\nPista iluminada'}),
            'notas': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Solo visible para el equipo'}),
        }

    def __init__(self, *args, usuario=None, fecha=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        agencia = usuario.agencia if usuario and usuario.agencia_id else None
        self.agencia = agencia
        self.modulos = modulos_de(agencia)

        # Solo sub-agencias de su agencia; quien pertenece a una sub-agencia registra a nombre de ella
        colaboradores = Colaborador.objects.filter(estado=True, agencia_id=agencia.pk if agencia else None)
        if usuario and not usuario.ve_todo:
            colaboradores = colaboradores.filter(pk=usuario.colaborador_id)
            if usuario.colaborador_id:
                self.fields['colaborador'].initial = usuario.colaborador_id
                self.fields['colaborador'].disabled = True
        self.fields['colaborador'].queryset = colaboradores
        self.fields['colaborador'].empty_label = 'Sin asignar'
        self.fields['tipo_evento'].choices = [c for c in self.fields['tipo_evento'].choices if c[0]]
        self.fields['etapa'].choices = [c for c in self.fields['etapa'].choices if c[0]]
        quitar = () if self.modulos['subagencias'] else ('colaborador',)
        if self.instance.pk:
            quitar += ('anticipo', 'anticipo_metodo', 'itinerario_base')  # al editar se usan las pestañas Pagos e Itinerario
        for campo in quitar:
            self.fields.pop(campo, None)

        if not self.instance.pk and not self.is_bound:
            dia = None
            if fecha:
                try:
                    dia = datetime.strptime(fecha[:10], '%Y-%m-%d').date()
                except ValueError:
                    dia = None
            if dia is None:
                hoy = timezone.localdate()
                dia = hoy + timedelta(days=(5 - hoy.weekday()) % 7 or 7)  # próximo sábado
            inicio = timezone.make_aware(datetime.combine(dia, time(19, 0)))
            self.initial.setdefault('fecha_inicio_evento', inicio)
            self.initial.setdefault('fecha_fin_evento', inicio + timedelta(hours=7))

        self.duraciones = DURACIONES
        # Sugerencias de lugares y clientes anteriores: el asistente muestra su propio panel (sin <datalist>,
        # que el navegador dibuja con una flecha de menú aunque no haya nada que sugerir)
        self.fields['lugar'].widget.attrs.update({'data-sugerencias': 'lugares', 'autocomplete': 'off'})
        self.fields['cliente_nombre'].widget.attrs.update({'data-sugerencias': 'clientes', 'autocomplete': 'off'})
        self._preparar_servicios(agencia)
        self.asistente = self._asistente(usuario)

    def _preparar_servicios(self, agencia):
        """Catálogo para elegir servicios y los renglones con los que abre el formulario."""
        agencia_id = agencia.pk if agencia else None
        self._servicios = {s.pk: s for s in Servicio.objects.filter(agencia_id=agencia_id)}
        self._paquetes = {p.pk: p for p in Paquete.objects.filter(agencia_id=agencia_id)}
        self.catalogo = json.dumps(datos_catalogo(agencia_id)) if self.modulos['cotizaciones'] and self._servicios else ''
        self.lineas = None  # se llenan en clean() si el formulario mandó sus conceptos
        guardados = list(self.instance.conceptos.all()) if self.instance.pk else []
        if self.is_bound:
            self.conceptos_iniciales = self.data.get('conceptos') or '[]'
        elif guardados:
            self.conceptos_iniciales = conceptos_json(guardados)
        else:  # eventos de antes: sus servicios escritos a mano entran como renglones sin precio
            self.conceptos_iniciales = json.dumps([
                {'servicio': None, 'paquete': None, 'descripcion': s[:160], 'detalle': '', 'cantidad': '1', 'unidad': '', 'precio': ''}
                for s in self.instance.lista_servicios]) if self.instance.pk else '[]'
        total = sum((c.importe for c in guardados), 0)
        # El precio sigue a los servicios mientras no se haya escrito a mano
        self.precio_automatico = not self.instance.pk or (bool(guardados) and abs(self.instance.precio_total - total) < 0.01)

    def _asistente(self, usuario):
        """Datos para que el formulario se adapte mientras se llena (ver initAsistenteEvento en em.js)."""
        nombres = dict(TipoEvento.choices)
        ajustes = Ajustes.de(self.agencia)
        extras = {}  # qué extras ya tiene el evento o con qué nace, para el resumen
        if self.modulos['en_vivo']:
            extras['en_vivo'] = {'nombre': 'Experiencia en vivo', 'activo': bool(self.instance.con_en_vivo) if self.instance.pk
                                 else ajustes.en_vivo_por_defecto}
        if self.modulos['invitaciones']:
            extras['invitacion'] = {'nombre': 'Invitación digital', 'activo': self.instance.pk is not None and tiene_invitacion(self.instance)}
        datos = {
            'tipos': {t: {'nombre': nombres.get(t, ''), 'etiqueta': e, 'ejemplo': ej, 'ayuda': a} for t, (e, ej, a) in TEXTOS_TIPO.items()},
            'etapas': ETAPAS,
            'duraciones': DURACIONES,
            'disponibilidad': reverse('eventos:disponibilidad'),
            'excepto': self.instance.pk,
            'modulos': self.modulos,
            'extras': extras,
            **(sugerencias(usuario) if usuario and usuario.is_authenticated else {'lugares': [], 'clientes': []}),
        }
        if 'itinerario_base' in self.fields:
            datos['itinerarios'] = {t: [(m, titulo, ActividadItinerario.ICONOS[icono]) for m, titulo, icono in lista]
                                    for t, lista in ITINERARIOS.items()}
        return json.dumps(datos)

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get('fecha_inicio_evento'), datos.get('fecha_fin_evento')
        if inicio and fin and fin <= inicio:
            self.add_error('fecha_fin_evento', 'La hora de término debe ser posterior al inicio.')
        if datos.get('precio_total') is not None and datos['precio_total'] < 0:
            self.add_error('precio_total', 'No puede ser negativo.')
        if inicio and self.instance.pk:
            self._validar_mes_de_fotos(inicio)
        if 'conceptos' in self.data:
            try:
                self.lineas = leer_conceptos(self.data.get('conceptos'), self._servicios, self._paquetes,
                                             precio_minimo=-Decimal('99999999'))
            except forms.ValidationError as error:
                self.add_error(None, error)
            else:
                datos['servicios'] = '\n'.join(ConceptoEvento(**c).texto_servicio for c in self.lineas)
        anticipo, precio = datos.get('anticipo'), datos.get('precio_total')
        if anticipo and precio is not None and anticipo > precio:
            self.add_error('anticipo', 'El anticipo no puede ser mayor al precio total.' if precio else 'Escribe primero el precio total.')
        return datos

    def _validar_mes_de_fotos(self, inicio):
        """Si el evento cambia de mes, las fotos que tiene apartadas deben caber en la bolsa del mes nuevo."""
        apartadas = self.instance.limite_fotos
        if not (self.instance.con_en_vivo and apartadas and bolsa_de(self.agencia) is not None):
            return
        nuevo, antes = timezone.localtime(inicio), timezone.localtime(self.instance.fecha_inicio_evento)
        if (nuevo.year, nuevo.month) == (antes.year, antes.month):
            return
        bolsa = bolsa_del_mes(self.agencia, nuevo.year, nuevo.month, excepto=self.instance)
        if apartadas > bolsa['libres']:
            self.add_error('fecha_inicio_evento', f'Este evento tiene {apartadas:,} fotos apartadas y en {bolsa["mes"]} solo '
                                                  f'quedan {bolsa["libres"]:,}. Ajusta sus fotos en la experiencia en vivo.')

    def save(self, commit=True):
        evento = super().save(commit=commit)
        if commit and self.lineas is not None:
            evento.conceptos.all().delete()
            ConceptoEvento.objects.bulk_create([ConceptoEvento(evento=evento, orden=i, **c) for i, c in enumerate(self.lineas)])
        return evento


class EnVivoForm(forms.ModelForm):
    """La experiencia en vivo de un evento: fondo de las pantallas, interacción, qué envían los invitados y proyector."""

    class Meta:
        model = Evento
        fields = ['banner', 'estado', 'mensaje_bienvenida', 'password_vip', 'cooldown', 'permitir_saludos', 'permitir_canciones',
                  'permitir_fotos', 'limite_fotos', 'moderar_pantalla', 'pantalla_contenido', 'pantalla_qr']
        widgets = {
            'banner': forms.RadioSelect,
            'mensaje_bienvenida': forms.TextInput(attrs={'placeholder': '¡Gracias por acompañarnos! Pide tu canción favorita.'}),
            'password_vip': forms.TextInput(attrs={'placeholder': 'Ej. padrinos2026', 'autocomplete': 'off'}),
            'cooldown': forms.NumberInput(attrs={'min': 0, 'max': 120, 'step': '0.5'}),
            'limite_fotos': forms.NumberInput(attrs={'min': 1, 'placeholder': 'Ej. 300'}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        agencia = usuario.agencia if usuario and usuario.agencia_id else None
        self.agencia = agencia
        self.modulos = modulos_de(agencia)
        # Fondos: los de su agencia y la biblioteca de EventPro (una sub-agencia, solo los suyos y los generales)
        agencia_id = agencia.pk if agencia else None
        banners = Banner.objects.disponibles_para(agencia_id).filter(estado=True)
        if usuario and not usuario.ve_todo:
            banners = banners.filter(Q(colaborador__isnull=True) | Q(colaborador_id=usuario.colaborador_id))
        if self.instance.banner_id:
            banners = banners | Banner.objects.disponibles_para(agencia_id).filter(pk=self.instance.banner_id)
        self.fields['banner'].queryset = banners.distinct()
        self.fields['banner'].empty_label = 'Sin fondo'
        self.fields['banner'].required = False
        # Si no llegan en el envío se conserva el valor actual (con la interacción apagada se ocultan)
        for campo in ('pantalla_contenido', 'pantalla_qr', 'cooldown'):
            self.fields[campo].required = False
        self.fields['estado'].help_text = ('Los invitados escanean el QR y te mandan canciones, saludos y fotos. '
                                           'Puedes pausarla o reanudarla en cualquier momento.')
        if not self.modulos['fotos']:
            for campo in ('permitir_fotos', 'limite_fotos'):
                self.fields.pop(campo, None)
        self.bolsa = None  # bolsa de fotos al mes del plan: aquí se apartan las de este evento
        if 'limite_fotos' in self.fields:
            self.fields['limite_fotos'].label = 'Fotos para este evento'
            total = bolsa_de(agencia)
            if total is None:
                self.fields['limite_fotos'].help_text = 'Cuántas fotos pueden subir los invitados. Vacío = sin límite.'
            else:
                self.fields['limite_fotos'].help_text = ''
                self.fields['limite_fotos'].widget.attrs.update({'max': total, 'data-bolsa-apartar': ''})
                fecha = timezone.localtime(self.instance.fecha_inicio_evento)
                bolsa = bolsa_del_mes(agencia, fecha.year, fecha.month, excepto=self.instance)
                clave = f'{fecha.year}-{fecha.month:02d}'
                self.bolsa = {**bolsa, 'json': json.dumps({'total': total, 'libres': {clave: bolsa['libres']}, 'fecha': clave})}

    def clean(self):
        for campo in ('pantalla_contenido', 'pantalla_qr'):
            if not self.cleaned_data.get(campo):
                self.cleaned_data[campo] = getattr(self.instance, campo)
        datos = super().clean()
        cooldown = datos.get('cooldown')
        if cooldown is None:
            datos['cooldown'] = self.instance.cooldown if self.instance.cooldown is not None else 2
        elif cooldown < 0:
            self.add_error('cooldown', 'No puede ser negativo.')
        if 'limite_fotos' in self.fields:
            self._validar_fotos(datos)
        else:
            self.instance.permitir_fotos = False  # sin fotos en el plan no se reciben
        return datos

    def _validar_fotos(self, datos):
        if not datos.get('permitir_fotos'):
            datos['limite_fotos'] = None  # sin fotos no se aparta nada de la bolsa
            return
        limite = datos.get('limite_fotos')
        if limite is None:
            return
        ya = fotos_subidas(self.instance)
        if limite < ya:
            self.add_error('limite_fotos', f'Este evento ya recibió {ya:,} fotos; no puedes apartar menos.')
            return
        if self.bolsa is None:
            return
        reduce = self.instance.limite_fotos is not None and limite <= self.instance.limite_fotos
        if limite > self.bolsa['libres'] and not reduce:
            self.add_error('limite_fotos', f'En {self.bolsa["mes"]} solo quedan {self.bolsa["libres"]:,} fotos libres '
                                           f'de tu bolsa de {self.bolsa["total"]:,} al mes.')


class ActividadForm(forms.ModelForm):
    class Meta:
        model = ActividadItinerario
        fields = ['hora', 'titulo', 'icono', 'descripcion']
        widgets = {
            'hora': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'titulo': forms.TextInput(attrs={'placeholder': 'Ej. Ceremonia religiosa'}),
            'icono': forms.RadioSelect,
            'descripcion': forms.TextInput(attrs={'placeholder': 'Ej. Parroquia San José'}),
        }


class PagoForm(forms.ModelForm):
    class Meta:
        model = Pago
        fields = ['monto', 'fecha', 'metodo', 'referencia']
        widgets = {
            'monto': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01', 'placeholder': '0.00'}),
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'metodo': forms.RadioSelect,
            'referencia': forms.TextInput(attrs={'placeholder': 'Ej. Anticipo · transferencia BBVA'}),
        }

    def clean_monto(self):
        monto = self.cleaned_data['monto']
        if monto <= 0:
            raise forms.ValidationError('El monto debe ser mayor a cero.')
        return monto


class ProyectorForm(forms.ModelForm):
    """Ajuste rápido de la pantalla del proyector (desde el detalle del evento)."""

    class Meta:
        model = Evento
        fields = ['pantalla_contenido', 'pantalla_qr', 'moderar_pantalla']
        widgets = {'pantalla_contenido': forms.RadioSelect, 'pantalla_qr': forms.RadioSelect}
