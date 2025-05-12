from django.db import models
from core.models import BaseModel

CHAT_ROLE_USER = "user"
CHAT_ROLE_ASSISTANT = "assistant"

CHAT_ROLE_CHOICES = (
    (CHAT_ROLE_USER, "User"),
    (CHAT_ROLE_ASSISTANT, "Assistant"),
)

class ChatRoom(BaseModel):
    name = models.CharField(max_length=255)

class Chat(BaseModel):
    message = models.TextField()
    role = models.CharField(max_length=50, choices=CHAT_ROLE_CHOICES, default=CHAT_ROLE_USER)
    contract = models.ForeignKey("documents.Contract", on_delete=models.SET_NULL, null=True)
    chatroom = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="chats")