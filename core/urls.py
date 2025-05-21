from django.contrib import admin
from django.urls import include, path

from .consumer import ChatConsumer, NotificationConsumer

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("documents.urls")),
]

websocket_urlpatterns = [
    path("ws/notifications/", NotificationConsumer.as_asgi()),
    path("ws/chat/<uuid:contract_id>/", ChatConsumer.as_asgi()),
]
