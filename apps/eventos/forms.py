import json
from datetime import datetime, time, timedelta

from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.banners.models import Banner
from apps.colaboradores.models import Colaborador
from apps.core.modulos import MESES, bolsa_de, bolsa_del_mes, bolsa_por_mes, fotos_subidas, modulos_de

from .models import ActividadItinerario, Evento, Pago

FORMATO_FECHA_HORA = '%Y-%m-%dT%H:%M'


def _fecha_hora(attrs=None):
    return forms.DateTimeInput(attrs={'type': 'datetime-local', **(attrs or {})}, format=FORMATO_FECHA_HORA)


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = [
            'nombre_evento', 'tipo_evento', 'etapa', 'colaborador',
            'fecha_inicio_evento', 'fecha_fin_evento', 'lugar', 'direccion', 'url_mapa', 'num_invitados',
            'cliente_nombre', 'cliente_telefono', 'cliente_email', 'precio_total', 'servicios', 'notas',
            'banner', 'estado', 'mensaje_bienvenida', 'password_vip', 'cooldown',
            'permitir_saludos', 'permitir_canciones', 'permitir_fotos', 'limite_fotos', 'moderar_pantalla',
            'pantalla_contenido', 'pantalla_qr',
        ]
        widgets = {
            'nombre_evento': forms.TextInput(attrs={'placeholder': 'Ej. Ana & Luis', 'maxlength': 200}),
            'tipo_evento': forms.RadioSelect,
            'etapa': forms.RadioSelect,
            'banner': forms.RadioSelect,
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
            'mensaje_bienvenida': forms.TextInput(attrs={'placeholder': '¡Gracias por acompañarnos! Pide tu canción favorita.'}),
            'password_vip': forms.TextInput(attrs={'placeholder': 'Ej. padrinos2026', 'autocomplete': 'off'}),
            'cooldown': forms.NumberInput(attrs={'min': 0, 'max': 120, 'step': '0.5'}),
            'limite_fotos': forms.NumberInput(attrs={'min': 1, 'placeholder': 'Ej. 300'}),
        }

    # Opciones de la experiencia en vivo (desaparecen si el plan de la agencia no la incluye)
    CAMPOS_EN_VIVO = ('estado', 'mensaje_bienvenida', 'password_vip', 'cooldown', 'permitir_saludos', 'permitir_canciones',
                      'permitir_fotos', 'limite_fotos', 'moderar_pantalla', 'pantalla_contenido', 'pantalla_qr')

    def __init__(self, *args, usuario=None, fecha=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario

        # Solo sub-agencias de su agencia; banners de su agencia y de la biblioteca de EventPro
        agencia_id = usuario.agencia_id if usuario else None
        colaboradores = Colaborador.objects.filter(estado=True, agencia_id=agencia_id)
        banners = Banner.objects.disponibles_para(agencia_id).filter(estado=True)
        if usuario and not usuario.ve_todo:
            colaboradores = colaboradores.filter(pk=usuario.colaborador_id)
            banners = banners.filter(Q(colaborador__isnull=True) | Q(colaborador_id=usuario.colaborador_id))
            if usuario.colaborador_id:
                self.fields['colaborador'].initial = usuario.colaborador_id
                self.fields['colaborador'].disabled = True
        if self.instance.pk and self.instance.banner_id:
            banners = banners | Banner.objects.disponibles_para(agencia_id).filter(pk=self.instance.banner_id)
        self.fields['colaborador'].queryset = colaboradores
        self.fields['colaborador'].empty_label = 'Sin asignar'
        self.fields['banner'].queryset = banners.distinct()
        self.fields['banner'].empty_label = 'Sin fondo'
        self.fields['banner'].required = False
        self.fields['tipo_evento'].choices = [c for c in self.fields['tipo_evento'].choices if c[0]]
        self.fields['etapa'].choices = [c for c in self.fields['etapa'].choices if c[0]]
        # Opciones del proyector: si no llegan en el envío se conserva el valor actual (o el de fábrica)
        for campo in ('pantalla_contenido', 'pantalla_qr'):
            self.fields[campo].required = False

        # Lo que no incluye el plan de la agencia no se ofrece
        agencia = usuario.agencia if usuario and usuario.agencia_id else None
        self.modulos = modulos_de(agencia)
        quitar = self.CAMPOS_EN_VIVO if not self.modulos['en_vivo'] else (('permitir_fotos', 'limite_fotos') if not self.modulos['fotos'] else ())
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

        self.agencia = agencia
        self.bolsa = None  # bolsa de fotos al mes del plan: el organizador aparta aquí las de este evento
        if 'limite_fotos' in self.fields:
            self.fields['limite_fotos'].label = 'Fotos para este evento'
            total = bolsa_de(agencia)
            if total is None:
                self.fields['limite_fotos'].help_text = 'Cuántas fotos pueden subir los invitados. Vacío = sin límite.'
            else:
                self.fields['limite_fotos'].help_text = ''
                self.fields['limite_fotos'].widget.attrs.update({'max': total, 'data-bolsa-apartar': ''})
                self.bolsa = self._bolsa_inicial(agencia, total)

    def _bolsa_inicial(self, agencia, total):
        """Libres por mes (para que el formulario lo actualice al cambiar la fecha) y el mes de la fecha actual."""
        hoy = timezone.localdate()
        meses = [((hoy.month - 1 + i) // 12 + hoy.year, (hoy.month - 1 + i) % 12 + 1) for i in range(24)]
        fecha = self.instance.fecha_inicio_evento if self.instance.pk else self.initial.get('fecha_inicio_evento')
        if self.is_bound:
            try:
                fecha = datetime.strptime(self.data.get('fecha_inicio_evento', '')[:10], '%Y-%m-%d')
            except ValueError:
                pass
        if fecha:
            fecha = timezone.localtime(fecha) if timezone.is_aware(fecha) else fecha
            meses.append((fecha.year, fecha.month))
        libres = bolsa_por_mes(agencia, sorted(set(meses)), excepto=self.instance)
        actual = libres.get(f'{fecha.year}-{fecha.month:02d}', total) if fecha else total
        return {
            'total': total, 'libres': actual, 'ocupadas': total - actual, 'mes': MESES[fecha.month - 1] if fecha else '',
            'json': json.dumps({'total': total, 'libres': libres}),
        }

    def clean(self):
        for campo in ('pantalla_contenido', 'pantalla_qr'):
            # (sin experiencia en vivo en el plan estos campos no existen en el formulario)
            if campo in self.fields and not self.cleaned_data.get(campo):
                self.cleaned_data[campo] = getattr(self.instance, campo)
        datos = super().clean()
        inicio, fin = datos.get('fecha_inicio_evento'), datos.get('fecha_fin_evento')
        if inicio and fin and fin <= inicio:
            self.add_error('fecha_fin_evento', 'La hora de término debe ser posterior al inicio.')
        cooldown = datos.get('cooldown')
        if cooldown is not None and cooldown < 0:
            self.add_error('cooldown', 'No puede ser negativo.')
        if datos.get('precio_total') is not None and datos['precio_total'] < 0:
            self.add_error('precio_total', 'No puede ser negativo.')
        if 'limite_fotos' in self.fields:
            self._validar_fotos(datos)
        if not self.modulos['fotos']:
            self.instance.permitir_fotos = False  # sin fotos en el plan no se reciben
        return datos

    def _validar_fotos(self, datos):
        if not datos.get('permitir_fotos'):
            datos['limite_fotos'] = None  # sin fotos no se aparta nada de la bolsa
            return
        limite, inicio = datos.get('limite_fotos'), datos.get('fecha_inicio_evento')
        if limite is None:
            return
        if self.instance.pk:
            ya = fotos_subidas(self.instance)
            if limite < ya:
                self.add_error('limite_fotos', f'Este evento ya recibió {ya:,} fotos; no puedes apartar menos.')
                return
        if self.bolsa is None or inicio is None:
            return
        fecha = timezone.localtime(inicio)
        bolsa = bolsa_del_mes(self.agencia, fecha.year, fecha.month, excepto=self.instance)
        anterior = self.instance.fecha_inicio_evento and timezone.localtime(self.instance.fecha_inicio_evento)
        reduce = (self.instance.pk and self.instance.limite_fotos is not None and limite <= self.instance.limite_fotos
                  and (anterior.year, anterior.month) == (fecha.year, fecha.month))
        if limite > bolsa['libres'] and not reduce:
            self.add_error('limite_fotos', f'En {bolsa["mes"]} solo quedan {bolsa["libres"]:,} fotos libres '
                                           f'de tu bolsa de {bolsa["total"]:,} al mes.')


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
