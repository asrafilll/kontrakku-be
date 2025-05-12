from django.db import models
from core.models import BaseModel

CONTRACT_PENDING = "PENDING"
CONTRACT_PROCESSING = "PROCESSING"
CONTRACT_DONE = "DONE"

CONTRACT_PROCESSING_STATUS = (
    (CONTRACT_PENDING, "Pending"),
    (CONTRACT_PROCESSING, "Processing"),
    (CONTRACT_DONE, "Done"),
)


class Contract(BaseModel):
    file_name = models.CharField(max_length=255)
    file_path = models.FileField(upload_to="documents/")
    status = models.CharField(max_length=50, choices=CONTRACT_PROCESSING_STATUS, default=CONTRACT_PENDING)
    raw_text = models.TextField(blank=True, null=True)
    summarized_text = models.TextField(blank=True, null=True)
