import re

from django import forms

from .models import Colaborador


class ColaboradorForm(forms.ModelForm):
    class Meta:
        model = Colaborador
        fields = [
            'nombre', 'tipo', 'ciudad', 'eslogan', 'descripcion',
            'responsable', 'telefono', 'email', 'whatsapp', 'facebook', 'instagram', 'tiktok', 'sitio_web',
            'logo_principal', 'logo_secundario', 'color_marca', 'estado',
        ]
        labels = {'nombre': 'Nombre comercial', 'eslogan': 'Eslogan'}
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej. Sonido Espectacular'}),
            'tipo': forms.RadioSelect,
            'ciudad': forms.TextInput(attrs={'placeholder': 'Ej. Puebla, Pue.'}),
            'eslogan': forms.TextInput(attrs={'placeholder': 'La frase que los identifica'}),
            'descripcion': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Servicios, experiencia, zonas de cobertura…'}),
            'responsable': forms.TextInput(attrs={'placeholder': 'Nombre de quien atiende'}),
            'telefono': forms.TextInput(attrs={'placeholder': '10 dígitos', 'inputmode': 'tel'}),
            'email': forms.EmailInput(attrs={'placeholder': 'contacto@agencia.com'}),
            'whatsapp': forms.TextInput(attrs={'placeholder': '10 dígitos para cotizaciones', 'inputmode': 'tel'}),
            'facebook': forms.URLInput(attrs={'placeholder': 'https://facebook.com/…'}),
            'instagram': forms.URLInput(attrs={'placeholder': 'https://instagram.com/…'}),
            'tiktok': forms.URLInput(attrs={'placeholder': 'https://tiktok.com/@…'}),
            'sitio_web': forms.URLInput(attrs={'placeholder': 'https://…'}),
            'color_marca': forms.TextInput(attrs={'maxlength': 7, 'placeholder': '#0098DA'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo'].choices = [c for c in self.fields['tipo'].choices if c[0]]

    def clean_color_marca(self):
        color = (self.cleaned_data.get('color_marca') or '').strip()
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise forms.ValidationError('Usa un color hexadecimal, por ejemplo #0098DA.')
        return color.upper()

    def clean_whatsapp(self):
        numero = self.cleaned_data.get('whatsapp') or ''
        digitos = ''.join(c for c in numero if c.isdigit())
        if numero and len(digitos) < 10:
            raise forms.ValidationError('Escribe al menos 10 dígitos.')
        return numero
