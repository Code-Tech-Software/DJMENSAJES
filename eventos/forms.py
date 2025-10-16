from django import forms
from .models import Evento, SonidoDJ ,Banner

class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        exclude = ['usuario']
        widgets = {
            'fecha_inicio_evento': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fecha_fin_evento': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class SonidoDJForm(forms.ModelForm):
    class Meta:
        model = SonidoDJ
        fields = '__all__'  # Incluir todos los campos del modelo en el formulario

class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = '__all__' # También puedes listar los campos: ['nombre', 'descripcion', ...]