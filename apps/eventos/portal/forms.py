from django import forms
from django.utils import timezone

from ..models import PortalCliente
from .musica import GENEROS, momentos_de

MAX_LINEAS = 60


class CuestionarioForm(forms.ModelForm):
    """El cuestionario musical que llena el cliente; los momentos especiales dependen del tipo de evento."""
    generos = forms.MultipleChoiceField(label='Géneros que les gustan', required=False, widget=forms.CheckboxSelectMultiple,
                                        choices=[(g, g) for g in GENEROS])

    class Meta:
        model = PortalCliente
        fields = ['imprescindibles', 'prohibidas', 'generos', 'ambiente', 'menciones', 'notas']
        widgets = {
            'imprescindibles': forms.Textarea(attrs={'class': 'input', 'rows': 5, 'maxlength': 3000, 'placeholder': 'Una por renglón, por ejemplo:\nCelebration – Kool & The Gang\nLa Bikina – Luis Miguel'}),
            'prohibidas': forms.Textarea(attrs={'class': 'input', 'rows': 3, 'maxlength': 2000, 'placeholder': 'Una por renglón'}),
            'ambiente': forms.RadioSelect,
            'menciones': forms.Textarea(attrs={'class': 'input', 'rows': 3, 'maxlength': 1500, 'placeholder': 'Ej. Padrinos: Jorge y Lety (se pronuncia "Leti")'}),
            'notas': forms.Textarea(attrs={'class': 'input', 'rows': 3, 'maxlength': 2000, 'placeholder': 'Ej. A la abuela le encanta Juan Gabriel; nada de reguetón durante la cena'}),
        }
        labels = {
            'imprescindibles': 'Canciones que no pueden faltar',
            'prohibidas': 'Canciones que NO quieren escuchar',
            'ambiente': '¿Cómo imaginan la fiesta?',
            'menciones': 'Nombres que el DJ debe mencionar',
            'notas': 'Algo más para tu DJ',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ambiente'].choices = list(PortalCliente.Ambiente.choices)
        self.fields['ambiente'].required = False
        guardados = self.instance.momentos or {}
        self.momentos = []
        for clave, nombre in momentos_de(self.instance.evento.tipo_evento):
            campo = f'momento_{clave}'
            self.fields[campo] = forms.CharField(label=nombre, required=False, max_length=150, initial=guardados.get(clave, ''),
                                                 widget=forms.TextInput(attrs={'class': 'input', 'placeholder': 'Canción – Artista', 'autocomplete': 'off'}))
            self.momentos.append(self[campo])

    def _lineas(self, campo):
        texto = self.cleaned_data.get(campo, '')
        if len([x for x in texto.splitlines() if x.strip()]) > MAX_LINEAS:
            raise forms.ValidationError(f'Hasta {MAX_LINEAS} canciones, una por renglón.')
        return texto.strip()

    def clean_imprescindibles(self):
        return self._lineas('imprescindibles')

    def clean_prohibidas(self):
        return self._lineas('prohibidas')

    def save(self, commit=True):
        portal = super().save(commit=False)
        # Se guardan los momentos del tipo actual; los de un tipo anterior se conservan
        momentos = dict(portal.momentos or {})
        for clave, _ in momentos_de(portal.evento.tipo_evento):
            cancion = self.cleaned_data.get(f'momento_{clave}', '').strip()
            if cancion:
                momentos[clave] = cancion
            else:
                momentos.pop(clave, None)
        portal.momentos = momentos
        portal.musica_el = timezone.now()
        if commit:
            portal.save()
        return portal


class PortalOpcionesForm(forms.ModelForm):
    """Lo que decide la agencia sobre el portal de un evento."""

    class Meta:
        model = PortalCliente
        fields = ['activo', 'mostrar_pagos', 'fecha_limite']
        widgets = {'fecha_limite': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['activo'].help_text = 'Apagado, el enlace deja de funcionar (puedes volver a encenderlo).'
        self.fields['mostrar_pagos'].help_text = 'Lo que lleva pagado, su saldo y tus datos para pagar.'
        self.fields['fecha_limite'].help_text = 'Vacío = hasta el día del evento. Después queda solo para consultar.'

    def clean_fecha_limite(self):
        fecha = self.cleaned_data.get('fecha_limite')
        if fecha and fecha > timezone.localdate(self.instance.evento.fecha_inicio_evento):
            raise forms.ValidationError('Debe ser antes del evento.')
        return fecha
