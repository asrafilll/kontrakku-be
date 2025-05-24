import os
import json

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import Contract
from .tasks import process_contract_task


@method_decorator(csrf_exempt, name="dispatch")
class ContractUploadAPI(View):
    def post(self, request, *args, **kwargs):
        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return JsonResponse({"error": "No file uploaded"}, status=400)

        contract = Contract(file_path=uploaded_file)
        contract.file_name = uploaded_file.name
        contract.save()

        process_contract_task(contract.id)

        return JsonResponse(
            {
                "success": True,
                "contract_id": str(contract.id),
                "status": contract.status,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class ContractStatusAPI(View):
    def get(self, request, contract_id, *args, **kwargs):
        try:
            contract = Contract.objects.get(id=contract_id)

            response = {
                "contract_id": str(contract.id),
                "file_name": contract.file_name,
                "status": contract.status,
                "created_at": contract.created_at,
                "updated_at": contract.updated_at,
            }

            if contract.status == "DONE":
                try:
                    response["summary"] = json.loads(contract.summarized_text)
                except json.JSONDecodeError:
                    response["summary"] = {"error": "Invalid JSON in summarized_text"}

            return JsonResponse(response)

        except Contract.DoesNotExist:
            return JsonResponse({"error": "Contract not found"}, status=404)


@method_decorator(csrf_exempt, name="dispatch")
class ContractRetrieveAPI(View):
    def get(self, request, *args, **kwargs):
        contracts = Contract.objects.all().order_by("-created_at")

        response = {
            "contracts": [
                {
                    "contract_id": str(contract.id),
                    "file_name": contract.file_name,
                    "processing_status": contract.status,
                    "created_at": contract.created_at,
                }
                for contract in contracts
            ]
        }

        return JsonResponse(response)
