from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/envivo/dj/(?P<token>[\w-]+)/$', consumers.DJConsumer.as_asgi()),
    re_path(r'^ws/envivo/(?P<codigo>[a-z0-9]+)/pantalla/$', consumers.PantallaConsumer.as_asgi()),
    re_path(r'^ws/envivo/(?P<codigo>[a-z0-9]+)/$', consumers.InvitadosConsumer.as_asgi()),
]
