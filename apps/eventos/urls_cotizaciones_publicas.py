"""La cotización que recibe el cliente (enlace con token, sin cuenta)."""
from django.urls import path

from .cotizacion import publica

urlpatterns = [
    path('<str:token>/', publica.cotizacion_publica, name='cotizacion_publica'),
    path('<str:token>/pdf/', publica.cotizacion_publica_pdf, name='cotizacion_publica_pdf'),
    path('<str:token>/aceptar/', publica.cotizacion_aceptar, name='cotizacion_aceptar'),
]
