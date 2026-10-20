from django import forms

from ..models import Cliente, normalizar_telefono


class ClienteForm(forms.ModelForm):
    """Ficha del cliente. No deja repetir a alguien que ya está (mismo teléfono o correo)."""

    class Meta:
        model = Cliente
        fields = ['nombre', 'telefono', 'email', 'origen', 'notas']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej. Ana García', 'maxlength': 150}),
            'telefono': forms.TextInput(attrs={'placeholder': '10 dígitos', 'inputmode': 'tel'}),
            'email': forms.EmailInput(attrs={'placeholder': 'cliente@correo.com'}),
            'notas': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ej. Prefiere WhatsApp · Factura a nombre de…'}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.fields['origen'].choices = [('', 'Sin especificar'), *Cliente.Origen.choices]

    def clean(self):
        datos = super().clean()
        otros = Cliente.objects.filter(agencia_id=self.usuario.agencia_id if self.usuario else None).exclude(pk=self.instance.pk)
        visibles = set(Cliente.objects.visibles_para(self.usuario).values_list('pk', flat=True)) if self.usuario else set()

        def ya_esta(otro, dato):
            if otro.pk in visibles:
                return f'Ya tienes a «{otro.nombre}» con este {dato}. Si es la misma persona, edita su ficha.'
            return f'Ya hay un cliente de la agencia con este {dato}.'

        telefono = normalizar_telefono(datos.get('telefono'))
        if len(telefono) >= 7:
            otro = otros.filter(telefono_normalizado=telefono).first()
            if otro:
                self.add_error('telefono', ya_esta(otro, 'teléfono'))
        email = (datos.get('email') or '').strip()
        if email:
            otro = otros.filter(email__iexact=email).first()
            if otro:
                self.add_error('email', ya_esta(otro, 'correo'))
        return datos


class FusionarForm(forms.Form):
    """Junta una ficha duplicada con esta: sus eventos y cotizaciones pasan aquí."""
    duplicado = forms.ModelChoiceField(label='Ficha duplicada', queryset=Cliente.objects.none(), empty_label='Elige al cliente…')

    def __init__(self, *args, cliente=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cliente = cliente
        otros = Cliente.objects.visibles_para(usuario).exclude(pk=cliente.pk).order_by('nombre')
        self.fields['duplicado'].queryset = otros
        self.fields['duplicado'].label_from_instance = lambda c: ' · '.join(x for x in (c.nombre, c.telefono, c.email) if x)
        # Propone primero al más parecido: mismo teléfono, mismo correo o mismo primer nombre y apellido
        parecido = None
        if cliente.telefono_normalizado:
            parecido = otros.filter(telefono_normalizado=cliente.telefono_normalizado).first()
        if parecido is None and cliente.email:
            parecido = otros.filter(email__iexact=cliente.email).first()
        if parecido is None:
            palabras = cliente.nombre.split()
            if palabras:
                parecidos = otros.filter(nombre__istartswith=palabras[0])
                for palabra in palabras[1:2]:
                    parecidos = parecidos.filter(nombre__icontains=palabra)
                parecido = parecidos.first()
        if parecido is not None and not self.is_bound:
            self.initial['duplicado'] = parecido.pk
        self.sugerido = parecido
