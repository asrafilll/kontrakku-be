import os

from mistralai import Mistral

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")

mistral = Mistral(api_key=MISTRAL_API_KEY)
