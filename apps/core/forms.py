import re

from django import forms

from .models import Ajustes

MAX_LOGO_MB = 4


class AjustesForm(forms.ModelForm):
    class Meta:
        model = Ajustes
        fields = [
            'nombre', 'eslogan', 'logo_principal', 'logo_secundario', 'color_marca',
            'whatsapp', 'telefono', 'email', 'sitio_web', 'instagram', 'facebook', 'tiktok',
            'cooldown', 'permitir_saludos', 'permitir_canciones', 'permitir_fotos', 'moderar_pantalla', 'mensaje_bienvenida',
            'plantilla', 'dias_limite_rsvp',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Nombre de tu agencia'}),
            'color_marca': forms.TextInput(attrs={'maxlength': 7, 'placeholder': '#0098DA'}),
            'eslogan': forms.TextInput(attrs={'placeholder': 'Hacemos vibrar tu fiesta'}),
            'whatsapp': forms.TextInput(attrs={'placeholder': '55 1234 5678', 'inputmode': 'tel'}),
            'telefono': forms.TextInput(attrs={'placeholder': '55 1234 5678', 'inputmode': 'tel'}),
            'email': forms.EmailInput(attrs={'placeholder': 'contacto@tunegocio.com'}),
            'sitio_web': forms.URLInput(attrs={'placeholder': 'https://…'}),
            'instagram': forms.URLInput(attrs={'placeholder': 'https://instagram.com/…'}),
            'facebook': forms.URLInput(attrs={'placeholder': 'https://facebook.com/…'}),
            'tiktok': forms.URLInput(attrs={'placeholder': 'https://tiktok.com/@…'}),
            'cooldown': forms.NumberInput(attrs={'min': 0, 'max': 60, 'step': '0.5'}),
            'mensaje_bienvenida': forms.TextInput(attrs={'placeholder': '¡Bienvenidos! Pide tu canción o manda un saludo'}),
            'dias_limite_rsvp': forms.NumberInput(attrs={'min': 0, 'max': 90}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['color_marca'].required = False  # vacío = el azul de siempre

    def clean_color_marca(self):
        color = (self.cleaned_data.get('color_marca') or '').strip() or '#0098DA'
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise forms.ValidationError('Usa un color hexadecimal, por ejemplo #0098DA.')
        return color.upper()

    def _logo(self, campo):
        archivo = self.cleaned_data.get(campo)
        if archivo and hasattr(archivo, 'size') and archivo.size > MAX_LOGO_MB * 1024 * 1024:
            raise forms.ValidationError(f'El logo pesa más de {MAX_LOGO_MB} MB.')
        return archivo

    def clean_logo_principal(self):
        return self._logo('logo_principal')

    def clean_logo_secundario(self):
        return self._logo('logo_secundario')

    def clean_whatsapp(self):
        numero = ''.join(c for c in self.cleaned_data.get('whatsapp', '') if c.isdigit())
        if numero and not 10 <= len(numero) <= 15:
            raise forms.ValidationError('Escribe el número con lada (10 a 15 dígitos).')
        return numero
