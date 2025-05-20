from django.urls import path
from .views import DocumentUploadView

urlpatterns = [
  path("documents/", DocumentUploadView.as_view(), name="documents")
]
