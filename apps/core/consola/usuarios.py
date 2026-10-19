"""Usuarios de toda la plataforma: de cada agencia y las cuentas de EventPro."""
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from apps.cuentas.models import Usuario

from ..bitacora import Accion, registrar
from ..mixins import FormularioModalMixin, respuesta_error, respuesta_ok
from ..models import Agencia
from . import PlataformaMixin, clave_temporal, recordar_acceso, solo_plataforma, tomar_acceso
from .forms import UsuarioConsolaForm


def _pagina_de(usuario):
    """Dónde se muestra el acceso nuevo: en su agencia o, si es de EventPro, en la lista de usuarios."""
    return f'agencia:{usuario.agencia_id}' if usuario.agencia_id else 'usuarios'


def _destino(usuario):
    return reverse('plataforma:agencia', args=[usuario.agencia_id]) if usuario.agencia_id else reverse('plataforma:usuarios')


@solo_plataforma
def usuarios(request):
    q = request.GET.get('q', '').strip()
    agencia = request.GET.get('agencia', '')
    rol = request.GET.get('rol', '')
    estado = request.GET.get('estado', '')
    lista = Usuario.objects.select_related('agencia', 'colaborador').order_by('-is_superuser', 'agencia__nombre', '-is_active', 'first_name', 'username')
    if q:
        lista = lista.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    if agencia == 'eventpro':
        lista = lista.filter(agencia__isnull=True)
    elif agencia.isdigit():
        lista = lista.filter(agencia_id=agencia)
    if rol in Usuario.Rol.values:
        lista = lista.filter(rol=rol, is_superuser=False)
    if estado == 'activos':
        lista = lista.filter(is_active=True)
    elif estado == 'inactivos':
        lista = lista.filter(is_active=False)
    return render(request, 'core/consola/usuarios.html', {
        'usuarios': lista[:300], 'total': lista.count(), 'acceso': tomar_acceso(request, 'usuarios'),
        'q': q, 'agencia': agencia, 'rol': rol, 'estado': estado,
        'agencias': Agencia.objects.order_by('nombre'), 'roles': Usuario.Rol.choices,
        'conteo': {
            'total': Usuario.objects.count(), 'eventpro': Usuario.objects.filter(is_superuser=True).count(),
            'activos': Usuario.objects.filter(is_active=True).count(), 'inactivos': Usuario.objects.filter(is_active=False).count(),
            'nunca': Usuario.objects.filter(last_login__isnull=True, is_active=True).count(),
        },
    })


class UsuarioFormMixin(PlataformaMixin, FormularioModalMixin):
    model = Usuario
    form_class = UsuarioConsolaForm
    template_modal = 'core/consola/form_usuario.html'
    icono = 'ph ph-user-gear'
    tamano = 'lg'

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'editor': self.request.user}


class UsuarioCrear(UsuarioFormMixin, CreateView):
    titulo = 'Nuevo usuario'
    subtitulo = 'De una agencia o de tu equipo de EventPro.'
    icono = 'ph ph-user-plus'
    texto_boton = 'Crear usuario'

    def get_initial(self):
        agencia = self.request.GET.get('agencia', '')
        return {**super().get_initial(), 'agencia': agencia if agencia.isdigit() else None, 'rol': Usuario.Rol.ADMIN, 'is_active': True}

    def form_valid(self, form):
        usuario = form.save(commit=False)
        clave = form.cleaned_data.get('clave') or clave_temporal()
        usuario.set_password(clave)
        usuario.save()
        registrar(Accion.USUARIO_CREADO, usuario=usuario,
                  detalle=f'@{usuario.username} · {"EventPro" if usuario.is_superuser else usuario.get_rol_display()}', request=self.request)
        recordar_acceso(self.request, usuario, clave, _pagina_de(usuario))
        return respuesta_ok(self.request, f'Usuario {usuario} creado.', redirect=_destino(usuario))


class UsuarioEditar(UsuarioFormMixin, UpdateView):
    titulo = 'Editar usuario'

    def get_subtitulo(self):
        return f'@{self.object.username}'

    def form_valid(self, form):
        cambios = ', '.join(str(form.fields[c].label) for c in form.changed_data)
        respuesta = super().form_valid(form)
        if cambios:
            registrar(Accion.USUARIO_EDITADO, usuario=self.object, detalle=f'Cambió: {cambios}', request=self.request)
        return respuesta


@solo_plataforma
@require_POST
def activar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario == request.user:
        return respuesta_error(request, 'No puedes desactivar tu propia cuenta.')
    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=['is_active'])
    registrar(Accion.USUARIO_ACTIVADO if usuario.is_active else Accion.USUARIO_DESACTIVADO, usuario=usuario, request=request)
    return respuesta_ok(request, f'{usuario} ahora está {"activo" if usuario.is_active else "inactivo"}.')


@solo_plataforma
@require_POST
def nueva_clave(request, pk):
    """Contraseña temporal nueva (p. ej. el administrador de una agencia la olvidó)."""
    usuario = get_object_or_404(Usuario, pk=pk)
    if usuario.is_superuser:
        return respuesta_error(request, 'Las cuentas de EventPro cambian su contraseña desde su perfil.')
    clave = clave_temporal()
    usuario.set_password(clave)
    usuario.save(update_fields=['password'])
    registrar(Accion.CLAVE, usuario=usuario, request=request)
    recordar_acceso(request, usuario, clave, _pagina_de(usuario))
    return respuesta_ok(request, f'Nueva contraseña para {usuario}.', redirect=_destino(usuario))
