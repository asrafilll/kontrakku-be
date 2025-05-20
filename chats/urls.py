from django.urls import path

from .views import ChatView

urlpatterns = [
   path('chat/<uuid:contract_id>/', ChatView.as_view(), name='chat'),
]