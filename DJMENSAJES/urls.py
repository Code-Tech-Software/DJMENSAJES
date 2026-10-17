from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.templatetags.static import static as url_estatica
from django.urls import include, path

admin.site.site_header = 'Grupo EM · Administración'
admin.site.site_title = 'Grupo EM'
admin.site.index_title = 'Panel técnico'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', lambda request: redirect(url_estatica('img/favicon.ico'), permanent=True)),

    # Panel interno
    path('', include('apps.core.urls')),
    path('', include('apps.cuentas.urls')),
    path('eventos/', include('apps.eventos.urls')),
    path('colaboradores/', include('apps.colaboradores.urls')),
    path('banners/', include('apps.banners.urls')),
    path('invitaciones/', include('apps.invitaciones.urls')),

    # Páginas públicas
    path('i/', include('apps.invitaciones.urls_publicas')),
    path('anfitriones/', include('apps.invitaciones.urls_anfitriones')),
    path('', include('apps.envivo.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = 'apps.core.views.error_403'
handler404 = 'apps.core.views.error_404'
handler500 = 'apps.core.views.error_500'
