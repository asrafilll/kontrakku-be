import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from whitenoise.middleware import WhiteNoiseMiddleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from .urls import websocket_urlpatterns

application = ProtocolTypeRouter(
    {"http": get_asgi_application(), "websocket": URLRouter(websocket_urlpatterns)}
)
