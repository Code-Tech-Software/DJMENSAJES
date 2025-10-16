# --- Librerías estándar ---
import io
import json
import base64
import qrcode

# --- Django: Atajos y utilidades ---
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.contrib import messages

# --- Django: Autenticación ---
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm

# --- Django: Vistas y decoradores ---
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, CreateView, UpdateView

# --- Django Channels ---
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

# --- Modelos y Formularios locales ---
from .models import Evento, SonidoDJ, Banner, Mensaje
from .forms import EventoForm, SonidoDJForm, BannerForm

def home(request):
    return render(request, 'home.html')

def registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'registro.html', {'form': form})

@login_required
def crear_evento(request):
    if request.method == 'POST':
        form = EventoForm(request.POST)
        if form.is_valid():
            evento = form.save(commit=False)
            evento.usuario = request.user
            evento.save()
            return redirect('mis_eventos')
    else:
        form = EventoForm()
    return render(request, 'eventos/crear_evento.html', {'form': form})

@login_required
def mis_eventos(request):
    eventos = Evento.objects.filter(usuario=request.user)
    return render(request, 'eventos/mis_eventos.html', {'eventos': eventos})

@login_required
def editar_evento(request, id):
    evento = get_object_or_404(Evento, id=id, usuario=request.user)
    if request.method == 'POST':
        form = EventoForm(request.POST, instance=evento)
        if form.is_valid():
            form.save()
            messages.success(request, "Evento actualizado correctamente.")
            return redirect('mis_eventos')
    else:
        form = EventoForm(instance=evento)
    return render(request, 'eventos/editar_evento.html', {'form': form, 'evento': evento})


def pantalla_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    return render(request, 'eventos/evento_pantalla.html', {'evento': evento})

@csrf_exempt
def enviar_mensaje(request, evento_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        nombre = data.get('nombre', '').strip() or 'Anónimo'
        tipo = data.get('tipo')
        texto = data.get('mensaje')
        vip = data.get('vip', False)

        evento = get_object_or_404(Evento, id=evento_id)

        # Guardar mensaje en la BD
        msg = Mensaje.objects.create(
            nombre=nombre,
            tipo=tipo,
            mensaje=texto,
            vip=vip,
            evento=evento
        )
        # Enviar mensaje en tiempo real al grupo WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"evento_{evento_id}",
            {
                "type": "nuevo_mensaje",
                "mensaje": {
                    "id": msg.id,
                    "nombre": msg.nombre,
                    "tipo": msg.tipo,
                    "mensaje": msg.mensaje,
                    "vip": msg.vip,
                    "evento_id": evento.id,
                },
            }
        )

        return JsonResponse({'ok': True, 'msg': 'Mensaje enviado con éxito 🎉'})
    return JsonResponse({'ok': False, 'msg': 'Método no permitido'}, status=405)



def panel_dj(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    return render(request, 'eventos/panel_dj.html', {'evento': evento})



def detalle_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)

    url_pantalla = request.build_absolute_uri(f"/eventos/evento/{evento.id}/")
    url_panel_dj = request.build_absolute_uri(f"/eventos/evento/{evento.id}/panel_dj/")

    # Generar el QR con la URL de la pantalla del evento
    qr = qrcode.make(url_pantalla)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, "eventos/detalle_evento.html", {
        "evento": evento,
        "url_pantalla": url_pantalla,
        "url_panel_dj": url_panel_dj,
        "qr_base64": qr_base64,
    })


@require_POST
def eliminar_evento(request, evento_id):
    evento = get_object_or_404(Evento, pk=evento_id)
    evento.delete()
    return redirect('mis_eventos')

# Vistas para el modelo SonidoDJ
class SonidoDJListView(ListView):
    model = SonidoDJ
    template_name = 'eventos/SonidoDJ/sonidodj_list.html'
    context_object_name = 'sonidos'

class SonidoDJCreateView(CreateView):
    model = SonidoDJ
    form_class = SonidoDJForm
    template_name = 'eventos/SonidoDJ/sonidodj_form.html'
    success_url = reverse_lazy('sonidodj_list')

class SonidoDJUpdateView(UpdateView):
    model = SonidoDJ
    form_class = SonidoDJForm
    template_name = 'eventos/SonidoDJ/sonidodj_form.html'
    success_url = reverse_lazy('sonidodj_list')
@require_POST # Solo permite peticiones POST
def sonidodj_eliminar(request, pk):
    sonido = get_object_or_404(SonidoDJ, pk=pk)
    sonido.delete()
    return redirect('sonidodj_list')

# Vistas para el modelo Banner
class BannerListView(ListView):
    model = Banner
    template_name = 'eventos/Banner/banner_list.html'
    context_object_name = 'banners'

class BannerCreateView(CreateView):
    model = Banner
    form_class = BannerForm
    template_name = 'eventos/Banner/banner_form.html'
    success_url = reverse_lazy('banner_list')
class BannerUpdateView(UpdateView):
    model = Banner
    form_class = BannerForm
    template_name = 'eventos/Banner/banner_form.html'
    success_url = reverse_lazy('banner_list')
@require_POST # Solo permite peticiones POST
def banner_eliminar(request, pk):
    banner = get_object_or_404(Banner, pk=pk)
    banner.delete()
    return redirect('banner_list')