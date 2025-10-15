from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/evento/(?P<evento_id>\d+)/$', consumers.EventoConsumer.as_asgi()),
]
