from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from eventos import views
from django.urls import re_path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registro/', views.registro, name='registro'),
    path('', views.home, name='home'),
    path('eventos/', include('eventos.urls')),

]
