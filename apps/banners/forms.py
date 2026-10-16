from django import forms

from apps.colaboradores.models import Colaborador

from .models import Banner


class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = ['nombre', 'categoria', 'colaborador', 'descripcion', 'fondo_movil', 'fondo_pantalla', 'portada', 'estado']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej. Dorado elegante'}),
            'descripcion': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Para qué tipo de eventos funciona mejor'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['colaborador'].queryset = Colaborador.objects.filter(estado=True)
        self.fields['colaborador'].empty_label = 'Disponible para todos'
        self.fields['colaborador'].label = 'Exclusivo de'

    def clean(self):
        datos = super().clean()
        tiene_imagen = any(
            datos.get(c) or (getattr(self.instance, c) and datos.get(c) is not False)
            for c in ('fondo_movil', 'fondo_pantalla', 'portada')
        )
        if not tiene_imagen:
            raise forms.ValidationError('Sube al menos una imagen para el banner.')
        return datos
