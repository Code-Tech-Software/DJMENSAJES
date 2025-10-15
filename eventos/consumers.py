import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import Mensaje, Evento
from asgiref.sync import sync_to_async

class EventoConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.evento_id = self.scope['url_route']['kwargs']['evento_id']
        self.evento_group_name = f"evento_{self.evento_id}"

        # Únete al grupo del evento
        await self.channel_layer.group_add(
            self.evento_group_name,
            self.channel_name
        )
        await self.accept()

        # Cargar mensajes antiguos y enviarlos al conectar
        mensajes = await self.obtener_mensajes()
        await self.send(text_data=json.dumps({
            'type': 'init',
            'mensajes': mensajes
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.evento_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        nombre = data.get('nombre', 'Anónimo')
        tipo = data.get('tipo')
        texto = data.get('mensaje')
        vip = data.get('vip', False)

        mensaje = await self.guardar_mensaje(nombre, tipo, texto, vip)

        # Enviar mensaje a todos los conectados
        await self.channel_layer.group_send(
            self.evento_group_name,
            {
                'type': 'nuevo_mensaje',
                'mensaje': mensaje
            }
        )

    async def nuevo_mensaje(self, event):
        mensaje = event['mensaje']
        await self.send(text_data=json.dumps({
            'type': 'mensaje',
            'mensaje': mensaje
        }))

    @sync_to_async
    def guardar_mensaje(self, nombre, tipo, texto, vip):
        evento = Evento.objects.get(id=self.evento_id)
        msg = Mensaje.objects.create(
            nombre=nombre,
            tipo=tipo,
            mensaje=texto,
            vip=vip,
            evento=evento
        )
        return {
            'id': msg.id,
            'nombre': msg.nombre,
            'tipo': msg.tipo,
            'mensaje': msg.mensaje,
            'vip': msg.vip,
            'evento_id': self.evento_id
        }

    @sync_to_async
    def obtener_mensajes(self):
        mensajes = Mensaje.objects.filter(evento_id=self.evento_id).order_by('-id')[:50]
        return [
            {
                'id': m.id,
                'nombre': m.nombre,
                'tipo': m.tipo,
                'mensaje': m.mensaje,
                'vip': m.vip,
            }
            for m in mensajes
        ]
