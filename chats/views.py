from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from documents.models import Contract

class ChatView(TemplateView):
    template_name = 'chats/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        contract_id = self.kwargs.get('contract_id')
        contract = get_object_or_404(Contract, id=contract_id)

        context['contract'] = contract
        context['messages'] = contract.chats.all().order_by('created_at')

        return context