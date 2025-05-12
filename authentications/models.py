from django.db import models
from core.models import BaseModel

class User(BaseModel):
    firstname = models.CharField(max_length=255)
    lastname = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.firstname} {self.lastname} ({self.email})"