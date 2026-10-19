from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm

from apps.colaboradores.models import Colaborador

from .models import Usuario


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Usuario',
        widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username', 'placeholder': 'tu.usuario'}),
    )
    password = forms.CharField(
        label='Contraseña', strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'placeholder': '••••••••'}),
    )
    recordarme = forms.BooleanField(required=False, initial=True)

    error_messages = {
        'invalid_login': 'Usuario o contraseña incorrectos. Revisa mayúsculas y vuelve a intentar.',
        'inactive': 'Esta cuenta está desactivada. Contacta a un administrador.',
    }


class PerfilForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'telefono', 'cargo', 'direccion', 'foto']
        labels = {'first_name': 'Nombre', 'last_name': 'Apellidos', 'email': 'Correo electrónico'}
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'Nombre'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Apellidos'}),
            'email': forms.EmailInput(attrs={'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'placeholder': '10 dígitos', 'inputmode': 'tel'}),
            'cargo': forms.TextInput(attrs={'placeholder': 'Ej. Coordinadora de eventos'}),
            'direccion': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Calle, número, colonia, ciudad'}),
        }


class CambiarContrasenaForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Contraseña actual'
        self.fields['new_password1'].label = 'Nueva contraseña'
        self.fields['new_password1'].help_text = 'Mínimo 6 caracteres.'
        self.fields['new_password2'].label = 'Confirmar nueva contraseña'
        self.fields['old_password'].widget.attrs.pop('autofocus', None)


class RestablecerContrasenaForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Nueva contraseña'
        self.fields['new_password1'].help_text = 'Compártela con la persona de forma segura. Podrá cambiarla desde su perfil.'
        self.fields['new_password2'].label = 'Confirmar contraseña'


class UsuarioForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Contraseña', required=False, strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'placeholder': 'Mínimo 6 caracteres'}),
    )
    password2 = forms.CharField(
        label='Confirmar contraseña', required=False, strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'placeholder': 'Repite la contraseña'}),
    )

    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'username', 'email', 'telefono', 'cargo', 'rol', 'colaborador', 'is_active']
        labels = {
            'first_name': 'Nombre', 'last_name': 'Apellidos', 'username': 'Usuario',
            'email': 'Correo electrónico', 'is_active': 'Cuenta activa',
        }
        help_texts = {
            'username': 'Con este nombre iniciará sesión. Sin espacios.',
            'is_active': 'Si la desactivas no podrá iniciar sesión.',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'Nombre'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Apellidos'}),
            'username': forms.TextInput(attrs={'placeholder': 'ej. maria.lopez', 'autocomplete': 'off'}),
            'email': forms.EmailInput(attrs={'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'placeholder': '10 dígitos', 'inputmode': 'tel'}),
            'cargo': forms.TextInput(attrs={'placeholder': 'Ej. DJ residente'}),
            'rol': forms.RadioSelect,
        }

    usa_agencia = True

    def __init__(self, *args, agencia_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['colaborador'].queryset = Colaborador.objects.filter(estado=True, agencia_id=agencia_id)
        self.fields['colaborador'].empty_label = 'Sin sub-agencia (equipo central)'
        self.es_nuevo = not self.instance.pk
        if self.es_nuevo:
            self.fields['password1'].required = True
            self.fields['password2'].required = True

    def clean(self):
        datos = super().clean()
        if datos.get('rol') == Usuario.Rol.COLABORADOR and not datos.get('colaborador'):
            self.add_error('colaborador', 'Un usuario con rol Colaborador debe pertenecer a una sub-agencia.')
        p1, p2 = datos.get('password1'), datos.get('password2')
        if p1 or p2:
            if p1 != p2:
                self.add_error('password2', 'Las contraseñas no coinciden.')
            elif len(p1) < 6:
                self.add_error('password1', 'Usa al menos 6 caracteres.')
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get('password1'):
            usuario.set_password(self.cleaned_data['password1'])
        if commit:
            usuario.save()
        return usuario
