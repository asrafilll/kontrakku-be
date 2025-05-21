import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from .models import Contract
from .tasks import process_contract_task

class DocumentUploadAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        # Handle file upload
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return JsonResponse({'error': 'No file uploaded'}, status=400)

        # Create contract record
        contract = Contract(file_path=uploaded_file)
        contract.file_name = uploaded_file.name
        contract.save()

        # Trigger async processing
        process_contract_task(contract.id)

        return JsonResponse({
            'success': True,
            'contract_id': str(contract.id),
            'status': contract.status
        })


class DocumentStatusAPI(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request, contract_id):
        try:
            contract = Contract.objects.get(id=contract_id)

            response = {
                'contract_id': str(contract.id),
                'file_name': contract.file_name,
                'status': contract.status,
                'created_at': contract.created_at,
                'updated_at': contract.updated_at,
            }

            # Include summary if processing is complete
            if contract.status == 'DONE':
                response['summary'] = contract.summarized_text

            return JsonResponse(response)

        except Contract.DoesNotExist:
            return JsonResponse({'error': 'Contract not found'}, status=404)