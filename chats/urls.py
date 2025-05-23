from django.urls import path

from .api import ChatRetrieveAPI
from .views import ChatView

urlpatterns = [
    path("chat/<uuid:contract_id>/", ChatView.as_view(), name="chat"),
    path(
        "api/v1/chats/<uuid:contract_id>/",
        ChatRetrieveAPI.as_view(),
        name="chat_retrieve_api",
    ),
]
