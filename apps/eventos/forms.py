from datetime import datetime, time, timedelta

from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.banners.models import Banner
from apps.colaboradores.models import Colaborador

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
            'permitir_saludos', 'permitir_canciones', 'permitir_fotos', 'moderar_pantalla',
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
        }

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

    def clean(self):
        for campo in ('pantalla_contenido', 'pantalla_qr'):
            if not self.cleaned_data.get(campo):
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
        return datos


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
