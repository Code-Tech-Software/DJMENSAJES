# Grupo EM · Plataforma de eventos

Panel para administrar eventos y sub-agencias, invitaciones digitales con confirmación
(RSVP) y la experiencia en vivo: los invitados escanean un QR, piden canciones o mandan
saludos y le llegan al DJ en tiempo real.

## Estructura

```
DJMENSAJES/          configuración del proyecto (settings, urls, asgi)
apps/
  core/              dashboard, búsqueda (Ctrl+K), notificaciones, utilidades, mixins de modales
  cuentas/           usuario, login, perfil, equipo y roles
  colaboradores/     sub-agencias (marca, contacto, redes, logos)
  banners/           fondos para pantallas e invitaciones
  eventos/           eventos, calendario, itinerario, pagos, orden de servicio
  invitaciones/      invitación digital con editor en vivo (lugares, personas, galería, música),
                     lista de invitados, RSVP, pases QR y registro de entrada
  envivo/            pantalla de invitados, panel del DJ, proyector y WebSockets
templates/           layouts y componentes compartidos
static/css, js       sistema de diseño propio (sin Bootstrap)
```

## Roles

| Rol | Qué ve |
| --- | --- |
| Administrador | Todo, incluido el equipo y sus roles |
| Coordinador | Todos los eventos, colaboradores y banners |
| Colaborador | Solo los eventos de su sub-agencia |

## Desarrollo local

Sin variables de entorno el proyecto usa SQLite, canales en memoria y archivos en `media/`.

```bash
python manage.py migrate
python manage.py datos_demo      # usuario "demo", contraseña "demo1234"
python manage.py runserver
```

`runserver` ya sirve WebSockets (Daphne está en `INSTALLED_APPS`).

## Variables de entorno (producción)

| Variable | Uso |
| --- | --- |
| `DATABASE_URL` | PostgreSQL |
| `REDIS_URL` | Capa de canales para tiempo real |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Imágenes |
| `SECRET_KEY` | Clave secreta propia (recomendado) |
| `DEBUG` | `False` en producción (recomendado) |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Dominios separados por comas (opcional) |

## Actualizar una base existente

Las migraciones reubican los modelos en sus nuevas apps **sin mover tablas**: los datos
se conservan. El comando `migrate` del proyecto prepara automáticamente el historial de
migraciones de bases creadas con la versión anterior. Antes de desplegar, respalda la base
de datos. El `Procfile` ejecuta `migrate` al iniciar.

Los QR y enlaces de la versión anterior (`/eventos/evento/<id>/`) redirigen a las nuevas
pantallas.
