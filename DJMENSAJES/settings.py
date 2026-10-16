"""
Configuración de Grupo EM · Plataforma de eventos.

Todo lo sensible se lee de variables de entorno (.env en local, variables del
servicio en Railway). Cuando una integración no está configurada se usa un
respaldo local para poder desarrollar sin depender de servicios externos:

* DATABASE_URL vacío      -> SQLite (db.sqlite3)
* REDIS_URL vacío         -> capa de canales en memoria
* CLOUDINARY_* vacío      -> archivos en la carpeta /media
"""
from pathlib import Path
import os

import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(nombre, defecto=False):
    valor = os.getenv(nombre)
    if valor is None or valor == '':
        return defecto
    return valor.strip().lower() in ('1', 'true', 'yes', 'si', 'on')


def env_list(nombre, defecto):
    valor = os.getenv(nombre)
    if not valor:
        return defecto
    return [item.strip() for item in valor.split(',') if item.strip()]


SECRET_KEY = os.getenv(
    'SECRET_KEY',
    'django-insecure-p6$h2#v7hk5p$9x-c*m-#as8j$g!i$g4ndw$_^h8l)%22$)0$n',
)
DEBUG = env_bool('DEBUG', True)

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', ['*'])

CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', [
    "https://grupoem.up.railway.app",
    "https://www.grupoem.site",
    "https://grupoem.site",
])

CLOUDINARY_ACTIVO = bool(os.getenv('CLOUDINARY_CLOUD_NAME'))

INSTALLED_APPS = [
    # daphne debe ir primero: convierte runserver en un servidor ASGI (websockets)
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'channels',

    # Apps del proyecto
    'apps.core',
    'apps.cuentas',
    'apps.colaboradores',
    'apps.banners',
    'apps.eventos',
    'apps.invitaciones',
    'apps.envivo',
]

if CLOUDINARY_ACTIVO:
    INSTALLED_APPS += ['cloudinary', 'cloudinary_storage']

AUTH_USER_MODEL = 'cuentas.Usuario'
LOGIN_URL = 'cuentas:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'cuentas:login'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'DJMENSAJES.urls'

# La vista previa de la invitación se muestra en un iframe del propio panel
X_FRAME_OPTIONS = 'SAMEORIGIN'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.interfaz',
            ],
        },
    },
]

WSGI_APPLICATION = 'DJMENSAJES.wsgi.application'
ASGI_APPLICATION = 'DJMENSAJES.asgi.application'

# --- Canales en tiempo real -------------------------------------------------
REDIS_URL = os.getenv('REDIS_URL')
if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [REDIS_URL]},
        },
    }
else:
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

# --- Base de datos ------------------------------------------------------------
#DATABASES = {
#    'default': {
#        'ENGINE': 'django.db.backends.sqlite3',
#        'NAME': BASE_DIR / 'db.sqlite3',
#    }
#}

DATABASES = {
    'default': dj_database_url.config(default=os.getenv("DATABASE_URL"))
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Sesiones: "Recordarme" en el login las extiende a 30 días
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30

TIME_ZONE = 'America/Mexico_City'
LANGUAGE_CODE = 'es-mx'
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True

# --- Archivos estáticos y multimedia ---------------------------------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {
        'BACKEND': (
            'cloudinary_storage.storage.MediaCloudinaryStorage'
            if CLOUDINARY_ACTIVO else 'django.core.files.storage.FileSystemStorage'
        ),
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
}

# En desarrollo los estáticos no se guardan en caché del navegador (cambios visibles al instante)
if DEBUG:
    WHITENOISE_MAX_AGE = 0

DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MESSAGE_TAGS = {
    40: 'error',
}
