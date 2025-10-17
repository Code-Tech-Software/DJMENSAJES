from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from eventos import views
from django.urls import re_path

from eventos.views import iniciar_sesion

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', iniciar_sesion, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registro/', views.registro, name='registro'),
    path('', views.home, name='home'),
    path('eventos/', include('eventos.urls')),

]
# Para servir archivos multimedia en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
