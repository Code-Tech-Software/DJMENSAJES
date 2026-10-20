from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.templatetags.static import static as url_estatica
from django.urls import include, path

from apps.banners import urls as urls_banners
from apps.colaboradores import urls as urls_colaboradores
from apps.core import urls as urls_core
from apps.core.acceso import agencia_vigente, decorar_urls
from apps.core.modulos import requiere_modulo
from apps.cuentas import urls as urls_cuentas
from apps.eventos import urls as urls_eventos
from apps.eventos import urls_clientes, urls_cotizaciones
from apps.invitaciones import urls as urls_invitaciones

admin.site.site_header = 'EventPro · Administración'
admin.site.site_title = 'EventPro'
admin.site.index_title = 'Panel técnico'

# El panel de una agencia suspendida o vencida queda bloqueado (las páginas públicas no). Ver apps/core/acceso.py
for modulo in (urls_core, urls_eventos, urls_clientes, urls_cotizaciones, urls_colaboradores, urls_banners, urls_invitaciones):
    decorar_urls(modulo.urlpatterns, agencia_vigente)
decorar_urls(urls_cuentas.urlpatterns, agencia_vigente, excepto={'login', 'logout'})

# Secciones que dependen del plan de la agencia. Ver apps/core/modulos.py
decorar_urls(urls_invitaciones.urlpatterns, requiere_modulo('invitaciones'))
decorar_urls(urls_banners.urlpatterns, requiere_modulo('banners'))
decorar_urls(urls_cotizaciones.urlpatterns, requiere_modulo('cotizaciones'))
decorar_urls(urls_eventos.urlpatterns, requiere_modulo('en_vivo'), solo={'centro_envivo', 'proyector', 'qr_png', 'alternar_estado', 'en_vivo', 'en_vivo_activar', 'en_vivo_desactivar'})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', lambda request: redirect(url_estatica('img/favicon.ico'), permanent=True)),

    # Panel de EventPro (dueño de la plataforma): agencias, vencimientos y suspensiones
    path('plataforma/', include('apps.core.urls_plataforma')),

    # Panel interno de cada agencia
    path('', include(urls_core)),
    path('', include(urls_cuentas)),
    path('eventos/', include(urls_eventos)),
    path('clientes/', include(urls_clientes)),
    path('cotizaciones/', include(urls_cotizaciones)),
    path('colaboradores/', include(urls_colaboradores)),
    path('banners/', include(urls_banners)),
    path('invitaciones/', include(urls_invitaciones)),

    # Páginas públicas
    path('i/', include('apps.invitaciones.urls_publicas')),
    path('anfitriones/', include('apps.invitaciones.urls_anfitriones')),
    path('c/', include('apps.eventos.urls_cotizaciones_publicas')),
    path('', include('apps.envivo.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = 'apps.core.views.error_403'
handler404 = 'apps.core.views.error_404'
handler500 = 'apps.core.views.error_500'
