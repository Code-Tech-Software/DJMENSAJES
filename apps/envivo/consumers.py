"""
WebSockets de solo lectura. Los mensajes se envían por HTTP (con validaciones,
tiempo de espera y CSRF) y aquí solo se difunden a quien está escuchando:

* ws/envivo/<codigo>/             invitados: cambios de estado de sus mensajes
* ws/envivo/<codigo>/pantalla/    proyector: saludos aprobados
* ws/envivo/dj/<token>/           panel del DJ: todos los mensajes
"""
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.eventos.models import Evento

from .servicios import grupo_dj, grupo_estado, grupo_pantalla


class BaseConsumer(AsyncWebsocketConsumer):
    grupo = None

    async def connect(self):
        evento_id = await self.obtener_evento()
        if not evento_id:
            await self.close(code=4004)
            return
        self.grupo = self.nombre_grupo(evento_id)
        await self.channel_layer.group_add(self.grupo, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if self.grupo:
            await self.channel_layer.group_discard(self.grupo, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Solo se responde al "ping" de mantenimiento de conexión
        if text_data == 'ping':
            await self.send(text_data='pong')

    async def difundir(self, evento):
        await self.send(text_data=json.dumps(evento['datos']))

    async def obtener_evento(self):
        raise NotImplementedError

    def nombre_grupo(self, evento_id):
        raise NotImplementedError


class InvitadosConsumer(BaseConsumer):
    @database_sync_to_async
    def obtener_evento(self):
        codigo = self.scope['url_route']['kwargs']['codigo']
        return Evento.objects.filter(codigo=codigo).values_list('pk', flat=True).first()

    def nombre_grupo(self, evento_id):
        return grupo_estado(evento_id)


class PantallaConsumer(InvitadosConsumer):
    def nombre_grupo(self, evento_id):
        return grupo_pantalla(evento_id)


class DJConsumer(BaseConsumer):
    @database_sync_to_async
    def obtener_evento(self):
        token = self.scope['url_route']['kwargs']['token']
        return Evento.objects.filter(token_dj=token).values_list('pk', flat=True).first()

    def nombre_grupo(self, evento_id):
        return grupo_dj(evento_id)
