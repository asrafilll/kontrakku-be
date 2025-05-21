from django.urls import path

from .api import ContractRetrieveAPI, ContractStatusAPI, ContractUploadAPI
from .views import DocumentUploadView

urlpatterns = [
    path("documents/", DocumentUploadView.as_view(), name="documents"),
    path(
        "api/v1/contracts/upload",
        ContractUploadAPI.as_view(),
        name="api_upload_contract",
    ),
    path(
        "api/v1/contracts",
        ContractRetrieveAPI.as_view(),
        name="api_get_all_contract",
    ),
    path(
        "api/v1/contracts/status/<uuid:contract_id>",
        ContractStatusAPI.as_view(),
        name="api_get_status_contract",
    ),
]
