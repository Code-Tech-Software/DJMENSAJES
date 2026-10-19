from django import forms
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.utils import timezone

from apps.cuentas.models import Usuario

from ..models import Agencia, Ajustes, PagoAgencia, Plan


class AgenciaForm(forms.ModelForm):
    class Meta:
        model = Agencia
        fields = ['nombre', 'plan', 'vence_el', 'activa', 'notas']
        labels = {'activa': 'Acceso activo'}
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej. DJ Fiesta Norte'}),
            'vence_el': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'notas': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Contacto de cobro, cómo paga, acuerdos…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        planes = Plan.objects.filter(activo=True)
        if self.instance.pk and self.instance.plan_id:
            planes = planes | Plan.objects.filter(pk=self.instance.plan_id)  # conserva un plan ya retirado
        self.fields['plan'].queryset = planes.distinct()
        self.fields['plan'].empty_label = 'Sin plan (sin límites)'


class DatosAdministradorMixin(forms.Form):
    """Primer usuario (administrador) de una agencia."""
    admin_nombre = forms.CharField(label='Nombre', max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Ej. Laura Treviño'}))
    admin_usuario = forms.CharField(
        label='Usuario', max_length=150, validators=[UnicodeUsernameValidator()],
        help_text='Con este nombre inicia sesión. Sin espacios.',
        widget=forms.TextInput(attrs={'placeholder': 'ej. laura.norte', 'autocomplete': 'off'}),
    )
    admin_correo = forms.EmailField(label='Correo', required=False, widget=forms.EmailInput(attrs={'placeholder': 'Opcional'}))
    admin_clave = forms.CharField(
        label='Contraseña temporal', required=False, strip=False,
        help_text='Déjala vacía y se genera una. Se muestra una sola vez para que se la compartas.',
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'placeholder': 'Se genera sola'}),
    )

    def clean_admin_usuario(self):
        usuario = self.cleaned_data['admin_usuario'].strip()
        if Usuario.objects.filter(username__iexact=usuario).exists():
            raise forms.ValidationError('Ese usuario ya existe. Prueba con otro.')
        return usuario

    def clean_admin_clave(self):
        clave = self.cleaned_data.get('admin_clave') or ''
        if clave and len(clave) < 8:
            raise forms.ValidationError('Usa al menos 8 caracteres (o déjala vacía para generarla).')
        return clave


class AgenciaNuevaForm(DatosAdministradorMixin, AgenciaForm):
    class Meta(AgenciaForm.Meta):
        fields = ['nombre', 'plan', 'vence_el', 'notas']


class AdministradorForm(DatosAdministradorMixin):
    pass


class ContactoPlataformaForm(forms.ModelForm):
    """WhatsApp y correo de EventPro: los ven las agencias por vencer o suspendidas para renovar."""
    class Meta:
        model = Ajustes
        fields = ['whatsapp', 'email']
        labels = {'whatsapp': 'WhatsApp de EventPro', 'email': 'Correo de EventPro'}
        widgets = {
            'whatsapp': forms.TextInput(attrs={'placeholder': '55 1234 5678', 'inputmode': 'tel'}),
            'email': forms.EmailInput(attrs={'placeholder': 'hola@eventpro.mx'}),
        }

    def clean_whatsapp(self):
        numero = ''.join(c for c in self.cleaned_data.get('whatsapp', '') if c.isdigit())
        if numero and not 10 <= len(numero) <= 15:
            raise forms.ValidationError('Escribe el número con lada (10 a 15 dígitos).')
        return numero


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = ['nombre', 'precio_mensual', 'max_eventos_mes', 'max_usuarios', 'max_colaboradores', 'descripcion', 'activo', 'orden']
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej. Básico, Pro, Agencia'}),
            'precio_mensual': forms.NumberInput(attrs={'min': 0, 'step': '1', 'placeholder': '499'}),
            'max_eventos_mes': forms.NumberInput(attrs={'min': 1, 'placeholder': 'Sin límite'}),
            'max_usuarios': forms.NumberInput(attrs={'min': 1, 'placeholder': 'Sin límite'}),
            'max_colaboradores': forms.NumberInput(attrs={'min': 0, 'placeholder': 'Sin límite'}),
            'descripcion': forms.TextInput(attrs={'placeholder': 'Ej. Para DJs que empiezan'}),
            'orden': forms.NumberInput(attrs={'min': 0}),
        }


class PagoForm(forms.ModelForm):
    reactivar = forms.BooleanField(label='Reactivar si está suspendida', required=False, initial=True)

    class Meta:
        model = PagoAgencia
        fields = ['agencia', 'monto', 'meses', 'fecha', 'metodo', 'referencia']
        widgets = {
            'monto': forms.NumberInput(attrs={'min': 0, 'step': '0.01', 'placeholder': '499'}),
            'meses': forms.NumberInput(attrs={'min': 1, 'max': 36}),
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'referencia': forms.TextInput(attrs={'placeholder': 'Folio, banco o nota'}),
        }

    def __init__(self, *args, agencia=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['agencia'].queryset = Agencia.objects.order_by('nombre')
        self.fields['fecha'].initial = timezone.localdate()
        if agencia is not None:  # desde la página de la agencia: ya está elegida
            self.fields['agencia'].initial = agencia.pk
            self.fields['agencia'].widget = forms.HiddenInput()
            if agencia.plan_id:
                self.fields['monto'].initial = agencia.plan.precio_mensual

    def clean_meses(self):
        meses = self.cleaned_data['meses']
        if not 1 <= meses <= 36:
            raise forms.ValidationError('Entre 1 y 36 meses.')
        return meses

    def clean_monto(self):
        monto = self.cleaned_data['monto']
        if monto < 0:
            raise forms.ValidationError('El monto no puede ser negativo.')
        return monto


class UsuarioConsolaForm(forms.ModelForm):
    """Cualquier usuario de la plataforma: de una agencia o cuenta de EventPro (superusuario)."""
    clave = forms.CharField(
        label='Contraseña temporal', required=False, strip=False,
        help_text='Déjala vacía y se genera una. Se muestra una sola vez.',
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'placeholder': 'Se genera sola'}),
    )

    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'username', 'email', 'agencia', 'rol', 'is_active', 'is_superuser']
        labels = {
            'first_name': 'Nombre', 'last_name': 'Apellidos', 'username': 'Usuario', 'email': 'Correo',
            'is_active': 'Cuenta activa', 'is_superuser': 'Cuenta de EventPro (acceso total a la consola)',
        }
        help_texts = {
            'username': 'Con este nombre inicia sesión. Sin espacios.',
            'is_superuser': 'Solo para tu equipo de EventPro: ve y administra todas las agencias.',
        }
        widgets = {'rol': forms.RadioSelect}

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        self.fields['first_name'].required = True
        self.fields['agencia'].queryset = Agencia.objects.order_by('nombre')
        self.fields['agencia'].empty_label = 'Ninguna (cuenta de EventPro)'
        if self.instance.pk:
            del self.fields['clave']

    def clean(self):
        datos = super().clean()
        if not datos.get('is_superuser') and not datos.get('agencia'):
            self.add_error('agencia', 'Elige su agencia (solo las cuentas de EventPro van sin agencia).')
        if self.instance.pk and self.editor and self.instance.pk == self.editor.pk:
            if not datos.get('is_superuser'):
                self.add_error('is_superuser', 'No puedes quitarte tu propio acceso a la consola.')
            if not datos.get('is_active'):
                self.add_error('is_active', 'No puedes desactivar tu propia cuenta.')
        clave = datos.get('clave') or ''
        if clave and len(clave) < 8:
            self.add_error('clave', 'Usa al menos 8 caracteres (o déjala vacía para generarla).')
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.instance.pk is None or 'agencia' in self.changed_data:
            usuario.colaborador = None  # su sub-agencia era de la agencia anterior
        usuario.is_staff = usuario.is_superuser  # el admin técnico solo para EventPro
        if commit:
            usuario.save()
        return usuario
