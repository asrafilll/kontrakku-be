import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.core.wsgi import get_wsgi_application  # optional fallback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# Don't import routing at top-level!
django_application = get_asgi_application()

# Import AFTER Django is ready
from core.urls import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_application,
        "websocket": URLRouter(websocket_urlpatterns),
    }
)

## Yak betul fixingan dibantu chatgpt but it works yey
