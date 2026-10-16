import json
import math
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_GET, require_POST

from apps.core.utils import ip_cliente, qr_svg
from apps.eventos.models import Evento

from .models import Mensaje
from .servicios import notificar_cambio, notificar_evento, notificar_nuevo

MAX_INTENTOS_VIP = 5
BLOQUEO_VIP_SEG = 300


def _evento(codigo):
    return get_object_or_404(Evento.objects.select_related('colaborador', 'banner'), codigo=codigo)


def _evento_dj(token):
    return get_object_or_404(Evento.objects.select_related('colaborador', 'banner'), token_dj=token)


def _sesion(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def _es_vip(request, evento):
    return bool(evento.password_vip) and evento.pk in request.session.get('envivo_vip', [])


def _espera_restante(request, evento):
    """Segundos que faltan para que este invitado pueda enviar otro mensaje."""
    if _es_vip(request, evento) or evento.cooldown <= 0:
        return 0
    ultimo = (Mensaje.objects.filter(evento=evento, sesion=_sesion(request), vip=False)
              .order_by('-fecha_creacion').values_list('fecha_creacion', flat=True).first())
    if not ultimo:
        return 0
    restante = evento.cooldown * 60 - (timezone.now() - ultimo).total_seconds()
    return max(0, math.ceil(restante))


def _limpiar(texto, largo):
    texto = re.sub(r'[\x00-\x1f\x7f]', ' ', str(texto or ''))
    return re.sub(r'\s+', ' ', texto).strip()[:largo]


def _datos(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body or '{}')
        except ValueError:
            return {}
    return request.POST


# --- Pantalla de invitados (celular) ------------------------------------------------------------

def invitado(request, codigo):
    evento = _evento(codigo)
    sesion = _sesion(request)
    mios = Mensaje.objects.filter(evento=evento, sesion=sesion).order_by('-fecha_creacion')[:20]
    return render(request, 'envivo/invitado.html', {
        'evento': evento,
        'colaborador': evento.colaborador,
        'banner': evento.banner,
        'es_vip': _es_vip(request, evento),
        'nombre': request.session.get('envivo_nombre', ''),
        'espera': _espera_restante(request, evento),
        'espera_total': int(evento.cooldown * 60),
        'mis_mensajes': [m.a_dict() for m in mios],
        'invitacion': getattr(evento, 'invitacion', None),
    })


@require_POST
def enviar(request, codigo):
    evento = _evento(codigo)
    if not evento.estado:
        return JsonResponse({'ok': False, 'msg': 'En este momento el DJ no está recibiendo mensajes.'}, status=403)
    datos = _datos(request)
    tipo = datos.get('tipo')
    if tipo not in (Mensaje.Tipo.SALUDO, Mensaje.Tipo.CANCION):
        return JsonResponse({'ok': False, 'msg': 'Tipo de mensaje no válido.'}, status=400)
    if (tipo == Mensaje.Tipo.SALUDO and not evento.permitir_saludos) or (tipo == Mensaje.Tipo.CANCION and not evento.permitir_canciones):
        return JsonResponse({'ok': False, 'msg': 'Esta opción está desactivada para el evento.'}, status=403)

    texto = _limpiar(datos.get('mensaje'), 280)
    if len(texto) < 2:
        return JsonResponse({'ok': False, 'msg': 'Escribe tu mensaje.' if tipo == 'saludo' else 'Escribe el nombre de la canción.'}, status=400)
    nombre = _limpiar(datos.get('nombre'), 60) or request.session.get('envivo_nombre') or 'Anónimo'

    restante = _espera_restante(request, evento)
    if restante > 0:
        minutos, segundos = divmod(restante, 60)
        return JsonResponse({
            'ok': False, 'espera': restante,
            'msg': f'Podrás enviar otro mensaje en {minutos}:{segundos:02d} min.',
        }, status=429)

    vip = _es_vip(request, evento)
    mensaje = Mensaje.objects.create(
        evento=evento,
        nombre=nombre,
        tipo=tipo,
        mensaje=texto,
        artista=_limpiar(datos.get('artista'), 120) if tipo == Mensaje.Tipo.CANCION else '',
        destinatario=_limpiar(datos.get('destinatario'), 120) if tipo == Mensaje.Tipo.SALUDO else '',
        vip=vip,
        en_pantalla=tipo == Mensaje.Tipo.SALUDO and not evento.moderar_pantalla,
        sesion=_sesion(request),
        ip=ip_cliente(request),
    )
    request.session['envivo_nombre'] = nombre
    notificar_nuevo(mensaje)
    return JsonResponse({
        'ok': True,
        'msg': '¡Tu canción llegó al DJ! 🎶' if tipo == 'cancion' else '¡Tu saludo llegó al DJ! 💌',
        'mensaje': mensaje.a_dict(),
        'espera': 0 if vip else int(evento.cooldown * 60),
    })


@require_POST
def vip(request, codigo):
    evento = _evento(codigo)
    if not evento.password_vip:
        return JsonResponse({'ok': False, 'msg': 'Este evento no tiene acceso VIP.'}, status=400)
    ahora = timezone.now().timestamp()
    bloqueo = request.session.get('envivo_vip_bloqueo', 0)
    if bloqueo > ahora:
        return JsonResponse({'ok': False, 'msg': f'Demasiados intentos. Espera {math.ceil((bloqueo - ahora) / 60)} min.'}, status=429)

    password = _limpiar(_datos(request).get('password'), 100)
    if constant_time_compare(password.lower(), evento.password_vip.strip().lower()):
        vips = set(request.session.get('envivo_vip', []))
        vips.add(evento.pk)
        request.session['envivo_vip'] = list(vips)
        request.session['envivo_vip_intentos'] = 0
        return JsonResponse({'ok': True, 'msg': '¡Bienvenido a la zona VIP! 👑 Ya no tienes tiempo de espera.'})

    intentos = request.session.get('envivo_vip_intentos', 0) + 1
    request.session['envivo_vip_intentos'] = intentos
    if intentos >= MAX_INTENTOS_VIP:
        request.session['envivo_vip_bloqueo'] = ahora + BLOQUEO_VIP_SEG
        request.session['envivo_vip_intentos'] = 0
    return JsonResponse({'ok': False, 'msg': 'Contraseña incorrecta.'}, status=403)


@require_POST
def cambiar_nombre(request, codigo):
    _evento(codigo)
    nombre = _limpiar(_datos(request).get('nombre'), 60)
    request.session['envivo_nombre'] = nombre
    return JsonResponse({'ok': True, 'nombre': nombre})


@require_GET
def mis_mensajes(request, codigo):
    evento = _evento(codigo)
    mios = Mensaje.objects.filter(evento=evento, sesion=_sesion(request)).order_by('-fecha_creacion')[:20]
    return JsonResponse({
        'mensajes': [m.a_dict() for m in mios],
        'espera': _espera_restante(request, evento),
        'activo': evento.estado,
    })


# --- Proyector ------------------------------------------------------------------------------

def pantalla(request, codigo):
    evento = _evento(codigo)
    url_invitados = request.build_absolute_uri(evento.url_invitados())
    saludos = (Mensaje.objects.filter(evento=evento, en_pantalla=True)
               .exclude(estatus=Mensaje.Estatus.DESCARTADO).order_by('-fecha_creacion')[:16])
    return render(request, 'envivo/pantalla.html', {
        'evento': evento,
        'colaborador': evento.colaborador,
        'banner': evento.banner,
        'url_invitados': url_invitados,
        'url_corta': url_invitados.split('://', 1)[-1],
        'qr': qr_svg(url_invitados, color='#0b1220'),
        'saludos': [m.a_dict_pantalla() for m in reversed(list(saludos))],
    })


# --- Panel del DJ -------------------------------------------------------------------------

def dj(request, token):
    evento = _evento_dj(token)
    mensajes = evento.mensajes.order_by('-fecha_creacion')[:300]
    url_invitados = request.build_absolute_uri(evento.url_invitados())
    return render(request, 'envivo/dj.html', {
        'evento': evento,
        'mensajes': [m.a_dict() for m in mensajes],
        'url_invitados': url_invitados,
        'qr': qr_svg(url_invitados),
        'url_pantalla': request.build_absolute_uri(evento.url_pantalla()),
    })


@require_GET
def dj_mensajes(request, token):
    evento = _evento_dj(token)
    return JsonResponse({
        'mensajes': [m.a_dict() for m in evento.mensajes.order_by('-fecha_creacion')[:300]],
        'activo': evento.estado,
    })


ACCIONES = {
    'atender': {'estatus': Mensaje.Estatus.ATENDIDO},
    'pendiente': {'estatus': Mensaje.Estatus.PENDIENTE},
    'descartar': {'estatus': Mensaje.Estatus.DESCARTADO, 'en_pantalla': False},
    'restaurar': {'estatus': Mensaje.Estatus.PENDIENTE},
    'mostrar': {'en_pantalla': True},
    'ocultar': {'en_pantalla': False},
}


@require_POST
def dj_accion(request, token, pk, accion):
    evento = _evento_dj(token)
    if accion not in ACCIONES:
        return JsonResponse({'ok': False, 'msg': 'Acción no válida.'}, status=400)
    mensaje = get_object_or_404(Mensaje, pk=pk, evento=evento)
    cambios = ACCIONES[accion]
    if cambios.get('en_pantalla') and mensaje.tipo != Mensaje.Tipo.SALUDO:
        return JsonResponse({'ok': False, 'msg': 'Solo los saludos se muestran en el proyector.'}, status=400)
    pantalla_antes = mensaje.en_pantalla
    if 'estatus' in cambios:
        mensaje.marcar(cambios['estatus'])
    if 'en_pantalla' in cambios:
        mensaje.en_pantalla = cambios['en_pantalla']
    mensaje.save(update_fields=['estatus', 'atendido_en', 'en_pantalla'])
    notificar_cambio(mensaje, pantalla_cambio=pantalla_antes != mensaje.en_pantalla)
    return JsonResponse({'ok': True, 'mensaje': mensaje.a_dict()})


@require_POST
def dj_recepcion(request, token):
    evento = _evento_dj(token)
    evento.estado = not evento.estado
    evento.save(update_fields=['estado', 'actualizado'])
    notificar_evento(evento)
    return JsonResponse({'ok': True, 'activo': evento.estado})


# --- Enlaces anteriores (QR ya impresos) --------------------------------------------------------

def legado_invitados(request, evento_id):
    evento = get_object_or_404(Evento, pk=evento_id)
    return redirect('envivo:invitado', codigo=evento.codigo, permanent=True)


@login_required
def legado_dj(request, evento_id):
    evento = get_object_or_404(Evento.objects.visibles_para(request.user), pk=evento_id)
    return redirect(evento.url_dj())


def legado_pantalla(request, evento_id):
    evento = get_object_or_404(Evento, pk=evento_id)
    return redirect('envivo:pantalla', codigo=evento.codigo)
