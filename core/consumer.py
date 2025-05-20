from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from chats.models import Chat

from chats.tasks import process_chat
import json
import asyncio

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.channel_layer.group_add("notification", self.channel_name)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("notification", self.channel_name)

    async def send_notification(self, event):
        message = event["message"]
        await self.send(text_data=json.dumps({"message": message}))


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.contract_id = self.scope["url_route"]["kwargs"]["contract_id"]
        self.group_name  = f"chat_{self.contract_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg = data.get("message")
        if not msg:
            return
        process_chat(msg, self.contract_id)
    
    async def send_message(self, event):
        # Kirim pesan assistant ke client
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "sender": event.get("sender", "assistant")
        }))

    async def poll_assistant_reply(self):
        last_seen_id = await self.get_last_assistant_id()

        while True:
            await asyncio.sleep(2)

            latest = await self.get_latest_assistant()
            if latest and latest.id != last_seen_id:
                await self.send(text_data=json.dumps({
                    "message": latest.message,
                    "sender": "assistant",
                }))
                last_seen_id = latest.id

    @database_sync_to_async
    def get_latest_assistant(self):
        return Chat.objects.filter(
            contract_id=self.contract_id,
            role="assistant"
        ).order_by("-created_at").first()

    @database_sync_to_async
    def get_last_assistant_id(self):
        latest = Chat.objects.filter(
            contract_id=self.contract_id,
            role="assistant"
        ).order_by("-created_at").first()
        return latest.id if latest else None