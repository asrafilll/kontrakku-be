from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from .models import Contract
from .tasks import process_contract_task


class DocumentUploadView(View):
    template_name = "documents/index.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        uploaded_file = request.FILES.get("file_path")
        if not uploaded_file:
            return render(request, self.template_name, {"error": "No file uploaded"})

        contract = Contract(file_path=uploaded_file)
        contract.file_name = uploaded_file.name
        contract.save()

        process_contract_task(contract.id)
        return redirect(reverse("chat", kwargs={"contract_id": contract.id}))
