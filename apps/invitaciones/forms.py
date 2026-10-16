import re

from django import forms

from .models import Invitacion, Invitado, Mencion, Ubicacion


MAX_IMAGEN_MB = 8
MAX_AUDIO_MB = 10


def validar_peso(archivo, maximo_mb):
    if archivo and hasattr(archivo, 'size') and archivo.size > maximo_mb * 1024 * 1024:
        raise forms.ValidationError(f'El archivo pesa más de {maximo_mb} MB.')
    return archivo


class InvitacionForm(forms.ModelForm):
    """Todos los datos editables desde el editor (se guarda solo mientras escribes)."""

    class Meta:
        model = Invitacion
        fields = [
            'plantilla', 'color_principal', 'tipografia',
            'titulo', 'nombres', 'portada', 'texto_sobre',
            'frase', 'aviso', 'hashtag',
            'dress_code', 'mesa_regalos', 'regalos_url', 'musica', 'musica_titulo',
            'mostrar_contador', 'mostrar_itinerario', 'mostrar_mapa',
            'fecha_limite_rsvp', 'rsvp_abierto', 'publicada',
        ]
        widgets = {
            'plantilla': forms.RadioSelect,
            'tipografia': forms.RadioSelect,
            'color_principal': forms.TextInput(attrs={'maxlength': 7}),
            'titulo': forms.TextInput(attrs={'placeholder': 'Se sugiere según el tipo de evento'}),
            'nombres': forms.TextInput(attrs={'placeholder': 'Ej. Ana & Luis'}),
            'texto_sobre': forms.TextInput(attrs={'placeholder': 'Tienes una invitación especial'}),
            'frase': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Un mensaje o frase para tus invitados'}),
            'aviso': forms.TextInput(attrs={'placeholder': 'Ej. Evento solo para adultos'}),
            'hashtag': forms.TextInput(attrs={'placeholder': '#AnaYLuis2026'}),
            'dress_code': forms.TextInput(attrs={'placeholder': 'Ej. Formal · evitar blanco'}),
            'mesa_regalos': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Liverpool · Evento 51234567\nLluvia de sobres'}),
            'regalos_url': forms.URLInput(attrs={'placeholder': 'https://mesaderegalos.liverpool.com.mx/…'}),
            'musica_titulo': forms.TextInput(attrs={'placeholder': 'Ej. Perfect · Ed Sheeran'}),
            'fecha_limite_rsvp': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['musica'].widget.attrs['accept'] = 'audio/*'

    def clean_color_principal(self):
        color = (self.cleaned_data.get('color_principal') or '').strip()
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise forms.ValidationError('Usa un color hexadecimal, por ejemplo #B08D57.')
        return color.upper()

    def clean_hashtag(self):
        hashtag = re.sub(r'\s+', '', self.cleaned_data.get('hashtag') or '')
        if hashtag and not hashtag.startswith('#'):
            hashtag = '#' + hashtag
        return hashtag

    def clean_portada(self):
        return validar_peso(self.cleaned_data.get('portada'), MAX_IMAGEN_MB)

    def clean_musica(self):
        return validar_peso(self.cleaned_data.get('musica'), MAX_AUDIO_MB)


class UbicacionForm(forms.ModelForm):
    class Meta:
        model = Ubicacion
        fields = ['tipo', 'titulo', 'lugar', 'fecha', 'hora', 'direccion', 'url_mapa', 'notas', 'foto']
        widgets = {
            'tipo': forms.RadioSelect,
            'titulo': forms.TextInput(attrs={'placeholder': 'Ej. Misa de acción de gracias'}),
            'lugar': forms.TextInput(attrs={'placeholder': 'Ej. Parroquia de San Pedro Apóstol'}),
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'hora': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'direccion': forms.TextInput(attrs={'placeholder': 'Calle, número, colonia, ciudad'}),
            'url_mapa': forms.URLInput(attrs={'placeholder': 'https://maps.app.goo.gl/…'}),
            'notas': forms.TextInput(attrs={'placeholder': 'Ej. Estacionamiento en la parte trasera'}),
        }

    def clean_foto(self):
        return validar_peso(self.cleaned_data.get('foto'), MAX_IMAGEN_MB)


class MencionForm(forms.ModelForm):
    class Meta:
        model = Mencion
        fields = ['titulo', 'nombres']
        widgets = {
            'titulo': forms.TextInput(attrs={'placeholder': 'Ej. Padrinos de anillos', 'autocomplete': 'off'}),
            'nombres': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Rosa Martínez y Juan Pérez\nLaura Gómez'}),
        }


class InvitadoForm(forms.ModelForm):
    class Meta:
        model = Invitado
        fields = ['nombre', 'pases', 'telefono', 'email', 'grupo', 'mesa', 'notas', 'estado', 'pases_confirmados']
        labels = {'pases_confirmados': 'Pases confirmados', 'estado': 'Respuesta'}
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej. Familia Pérez López'}),
            'pases': forms.NumberInput(attrs={'min': 1, 'max': 50}),
            'telefono': forms.TextInput(attrs={'placeholder': '10 dígitos', 'inputmode': 'tel'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Opcional'}),
            'grupo': forms.TextInput(attrs={'placeholder': 'Ej. Familia novia', 'list': 'grupos-sugeridos'}),
            'mesa': forms.TextInput(attrs={'placeholder': 'Ej. 12'}),
            'notas': forms.TextInput(attrs={'placeholder': 'Ej. Menú vegetariano'}),
            'estado': forms.RadioSelect,
            'pases_confirmados': forms.NumberInput(attrs={'min': 0, 'max': 50}),
        }

    def clean(self):
        datos = super().clean()
        pases, confirmados = datos.get('pases') or 0, datos.get('pases_confirmados') or 0
        if pases < 1:
            self.add_error('pases', 'Asigna al menos 1 pase.')
        if confirmados > pases:
            self.add_error('pases_confirmados', 'No puede superar los pases asignados.')
        if datos.get('estado') == Invitado.Estado.CONFIRMADO and not confirmados:
            datos['pases_confirmados'] = pases
        if datos.get('estado') != Invitado.Estado.CONFIRMADO:
            datos['pases_confirmados'] = 0
        return datos


class ImportarInvitadosForm(forms.Form):
    lista = forms.CharField(
        label='Lista de invitados',
        widget=forms.Textarea(attrs={
            'rows': 9,
            'placeholder': 'Familia Pérez López, 4, 5512345678, Familia novia\nTía Rosy, 2\nCarlos Mendoza, 1, 5598765432',
            'style': 'font-family: var(--font-mono); font-size: 13px',
        }),
        help_text='Una invitación por línea: nombre, pases, WhatsApp, grupo (solo el nombre es obligatorio).',
    )
    grupo = forms.CharField(label='Grupo para todos', required=False,
                            widget=forms.TextInput(attrs={'placeholder': 'Opcional · se usa si la línea no indica grupo'}))

    def clean_lista(self):
        filas = []
        for numero, linea in enumerate(self.cleaned_data['lista'].splitlines(), start=1):
            linea = linea.strip()
            if not linea:
                continue
            partes = [p.strip() for p in re.split(r'[,;\t]', linea)]
            nombre = partes[0]
            if not nombre:
                raise forms.ValidationError(f'La línea {numero} no tiene nombre.')
            pases = 1
            if len(partes) > 1 and partes[1]:
                if not partes[1].isdigit() or not 1 <= int(partes[1]) <= 50:
                    raise forms.ValidationError(f'Línea {numero}: “{partes[1]}” no es un número de pases válido.')
                pases = int(partes[1])
            filas.append({
                'nombre': nombre[:150],
                'pases': pases,
                'telefono': partes[2][:30] if len(partes) > 2 else '',
                'grupo': partes[3][:60] if len(partes) > 3 else '',
            })
        if not filas:
            raise forms.ValidationError('Escribe al menos un invitado.')
        if len(filas) > 500:
            raise forms.ValidationError('Importa máximo 500 invitados a la vez.')
        return filas


class RSVPForm(forms.Form):
    asistira = forms.ChoiceField(choices=[('si', 'Sí asistiré'), ('no', 'No podré asistir')], widget=forms.RadioSelect)
    pases = forms.IntegerField(required=False)
    mensaje = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, maximo=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.maximo = maximo

    def clean(self):
        datos = super().clean()
        if datos.get('asistira') == 'si':
            # Nunca se confirman más pases de los asignados, aunque se manipule el formulario
            pases = datos.get('pases') or self.maximo
            datos['pases'] = max(1, min(pases, self.maximo))
        return datos


class RSVPAbiertoForm(RSVPForm):
    nombre = forms.CharField(max_length=150)
    telefono = forms.CharField(max_length=30, required=False)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('maximo', 10)
        super().__init__(*args, **kwargs)
