import os

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import Chat
from documents.models import Contract


@method_decorator(csrf_exempt, name="dispatch")
class ChatRetrieveAPI(View):
    def get(self, request, contract_id, n=20, *args, **kwargs):
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            return JsonResponse({"error": "Contract not found."}, status=404)

        chats = Chat.objects.filter(contract=contract).order_by("created_at")[:n]

        response = {
            "chats": [
                {
                    "role": chat.role,
                    "message": chat.message,
                    "created_at": chat.created_at.isoformat(),
                }
                for chat in chats
            ]
        }

        return JsonResponse(response)
