from django import forms

from .models import Ajustes


class AjustesForm(forms.ModelForm):
    class Meta:
        model = Ajustes
        fields = [
            'nombre', 'eslogan', 'whatsapp', 'telefono', 'email', 'sitio_web', 'instagram', 'facebook', 'tiktok',
            'cooldown', 'permitir_saludos', 'permitir_canciones', 'permitir_fotos', 'moderar_pantalla', 'mensaje_bienvenida',
            'plantilla', 'dias_limite_rsvp',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Grupo EM'}),
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

    def clean_whatsapp(self):
        numero = ''.join(c for c in self.cleaned_data.get('whatsapp', '') if c.isdigit())
        if numero and not 10 <= len(numero) <= 15:
            raise forms.ValidationError('Escribe el número con lada (10 a 15 dígitos).')
        return numero
