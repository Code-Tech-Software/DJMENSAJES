from django import forms
from .models import Evento

class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        exclude = ['usuario']
        widgets = {
            'fecha_inicio_evento': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'fecha_fin_evento': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
