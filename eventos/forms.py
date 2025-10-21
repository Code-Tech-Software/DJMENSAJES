from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Evento, SonidoDJ, Banner
from django.utils import timezone


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        exclude = ['usuario']
        widgets = {
            'nombre_evento': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Ingrese el nombre del evento'}),
            'tipo_evento': forms.Select(attrs={'class': 'form-control'}),
            'password_vip': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Contraseña para acceso VIP'}),
            'banner': forms.Select(attrs={'class': 'form-control'}),
            'sonido_dj': forms.Select(attrs={'class': 'form-control'}),
            'fecha_inicio_evento': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'fecha_fin_evento': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'cooldown': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'placeholder': 'Tiempo en minutos'}),
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super(EventoForm, self).__init__(*args, **kwargs)

        # Ajuste de formato para mostrar correctamente los datetime-local
        for field_name in ['fecha_inicio_evento', 'fecha_fin_evento']:
            if self.instance and getattr(self.instance, field_name):
                value = getattr(self.instance, field_name)
                if timezone.is_aware(value):
                    value = timezone.localtime(value)
                self.initial[field_name] = value.strftime('%Y-%m-%dT%H:%M')


class SonidoDJForm(forms.ModelForm):
    class Meta:
        model = SonidoDJ
        fields = [
            'nombre',  # Po si quieo cambiar el orden de apaicion
            'facebook',
            'whatsapp',
            'instagram',
            'tiktok',
            'imagen1',
            'eslogan',
            'imagen2',
            'estado',
        ]
        labels = {
            'imagen1': 'Logo Oscuro',
            'imagen2': 'Logo Claro',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del DJ o Sonido'}),
            'eslogan': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Eslogan o frase'}),
            'facebook': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'ULR'}),
            'whatsapp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de WhatsApp'}),
            'instagram': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'ULR'}),
            'tiktok': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'ULR'}),
            'imagen1': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'imagen2': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = [
            'nombre',
            'imagen1',
            'imagen2',
            'imagen3',
            'descripcion',
            'estado',
        ]
        labels = {
            'imagen1': 'F1',
            'imagen2': 'F2',
            'imagen3': 'F3',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del banner'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Descripción del banner'}),
            'imagen1': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'imagen2': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'imagen3': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
