"""El portal que recibe el cliente (enlace con token, sin cuenta)."""
from django.urls import path

from .portal import publica

urlpatterns = [
    path('<str:token>/', publica.portal, name='portal_cliente'),
    path('<str:token>/musica/', publica.portal_musica, name='portal_musica'),
]
