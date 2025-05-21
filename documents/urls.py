from django.urls import path

from .views import DocumentUploadView

from .api import DocumentUploadAPI, DocumentStatusAPI

urlpatterns = [
    path("documents/", DocumentUploadView.as_view(), name="documents"),
    path("api/documents/upload/", DocumentUploadAPI.as_view(), name="api_document_upload"),
    path("api/documents/<uuid:contract_id>/status/", DocumentStatusAPI.as_view(), name="api_document_status"),
]
