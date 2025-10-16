from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from .models import Evento
from .forms import EventoForm

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


from django.shortcuts import get_object_or_404
from django.contrib import messages

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


from django.http import JsonResponse
#SE VIENE LO PERRO
@login_required
def eliminar_evento(request, id):
    evento = get_object_or_404(Evento, id=id, usuario=request.user)
    if request.method == 'POST':
        evento.delete()
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=400)



def pantalla_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    return render(request, 'eventos/evento_pantalla.html', {'evento': evento})


import json
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from .models import Evento, Mensaje
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Mensaje, Evento


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

from django.shortcuts import render, get_object_or_404
from .models import Evento

def panel_dj(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    return render(request, 'eventos/panel_dj.html', {'evento': evento})

import qrcode
import io
import base64
from django.shortcuts import render, get_object_or_404
from .models import Evento  # Ajusta el import a tu modelo real
from django.urls import reverse

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

