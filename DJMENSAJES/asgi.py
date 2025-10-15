import os
from django.core.asgi import get_asgi_application

# 🔹 Configura Django ANTES de importar nada más
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DJMENSAJES.settings')

import django
django.setup()

# 🔹 Luego importa channels
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from eventos import routing as eventos_routing

# 🔹 Define la aplicación ASGI
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(eventos_routing.websocket_urlpatterns)
    ),
})
