from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, FormView, UpdateView

from apps.core.mixins import FormularioModalMixin, respuesta_error, respuesta_ok
from apps.eventos.models import Evento

from .forms import CambiarContrasenaForm, LoginForm, PerfilForm, RestablecerContrasenaForm, UsuarioForm
from .models import Usuario
from .permisos import AdminRequeridoMixin, admin_requerido


def iniciar_sesion(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    siguiente = request.POST.get('next') or request.GET.get('next') or ''
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        if not form.cleaned_data.get('recordarme'):
            request.session.set_expiry(0)  # expira al cerrar el navegador
        if siguiente and url_has_allowed_host_and_scheme(siguiente, {request.get_host()}):
            return redirect(siguiente)
        return redirect('core:dashboard')
    return render(request, 'cuentas/login.html', {'form': form, 'next': siguiente})


class CerrarSesion(auth_views.LogoutView):
    next_page = 'cuentas:login'


@login_required
def perfil(request):
    usuario = request.user
    eventos = Evento.objects.visibles_para(usuario)
    return render(request, 'cuentas/perfil.html', {
        'creados': Evento.objects.filter(creado_por=usuario).count(),
        'visibles': eventos.count(),
        'proximos': eventos.vigentes().proximos().order_by('fecha_inicio_evento')[:5],
    })


class EditarPerfil(LoginRequiredMixin, FormularioModalMixin, UpdateView):
    form_class = PerfilForm
    template_modal = 'cuentas/partials/form_perfil.html'
    titulo = 'Editar perfil'
    subtitulo = 'Actualiza tu información y foto.'
    icono = 'ph ph-user-gear'
    mensaje_exito = 'Perfil actualizado.'

    def get_object(self, queryset=None):
        return self.request.user


class CambiarContrasena(LoginRequiredMixin, FormularioModalMixin, FormView):
    form_class = CambiarContrasenaForm
    template_modal = 'cuentas/partials/form_contrasena.html'
    titulo = 'Cambiar contraseña'
    subtitulo = 'Por seguridad, confirma tu contraseña actual.'
    icono = 'ph ph-password'
    tamano = 'sm'
    texto_boton = 'Actualizar'
    mensaje_exito = 'Tu contraseña se actualizó.'
    recargar = False

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        usuario = form.save()
        update_session_auth_hash(self.request, usuario)
        return self.respuesta_exito()


# --- Gestión del equipo (solo administradores) --------------------------------------

@admin_requerido
def usuarios(request):
    q = request.GET.get('q', '').strip()
    rol = request.GET.get('rol', '')
    lista = Usuario.objects.select_related('colaborador').annotate(n_eventos=Count('eventos')).order_by('-is_active', 'first_name', 'username')
    if q:
        lista = lista.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    if rol:
        lista = lista.filter(rol=rol)
    conteo = dict(Usuario.objects.values_list('rol').annotate(n=Count('id')))
    return render(request, 'cuentas/usuarios.html', {
        'usuarios': lista, 'q': q, 'rol': rol, 'roles': Usuario.Rol.choices,
        'conteo': conteo, 'total': sum(conteo.values()),
    })


class UsuarioCrear(AdminRequeridoMixin, FormularioModalMixin, CreateView):
    model = Usuario
    form_class = UsuarioForm
    template_modal = 'cuentas/partials/form_usuario.html'
    titulo = 'Nuevo integrante'
    subtitulo = 'Crea el acceso y define qué podrá ver.'
    icono = 'ph ph-user-plus'
    tamano = 'lg'
    texto_boton = 'Crear usuario'
    mensaje_exito = 'Usuario creado. Ya puede iniciar sesión.'


class UsuarioEditar(AdminRequeridoMixin, FormularioModalMixin, UpdateView):
    model = Usuario
    form_class = UsuarioForm
    template_modal = 'cuentas/partials/form_usuario.html'
    icono = 'ph ph-user-gear'
    tamano = 'lg'
    mensaje_exito = 'Usuario actualizado.'

    def get_titulo(self):
        return f'Editar a {self.object}'

    def get_subtitulo(self):
        return f'@{self.object.username}'


class UsuarioContrasena(AdminRequeridoMixin, FormularioModalMixin, FormView):
    form_class = RestablecerContrasenaForm
    template_modal = 'cuentas/partials/form_contrasena.html'
    icono = 'ph ph-key'
    tamano = 'sm'
    texto_boton = 'Restablecer'
    mensaje_exito = 'Contraseña restablecida.'
    recargar = False

    def dispatch(self, request, *args, **kwargs):
        self.usuario = get_object_or_404(Usuario, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_titulo(self):
        return 'Restablecer contraseña'

    def get_subtitulo(self):
        return f'Asigna una nueva contraseña a {self.usuario}.'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.usuario
        return kwargs

    def form_valid(self, form):
        form.save()
        return self.respuesta_exito()


@admin_requerido
@require_POST
def usuario_activar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario == request.user:
        return respuesta_error(request, 'No puedes desactivar tu propia cuenta.')
    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=['is_active'])
    return respuesta_ok(request, f'{usuario} ahora está {"activo" if usuario.is_active else "inactivo"}.')
