import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")

class PromptManager:
    def __init__(
        self,
        messages: list[dict] | None = None,
        default_model: str = "gemini-2.5-flash-preview-05-20",
    ):
        self.messages = messages or []
        self.default_model = default_model

        # Gemini client uses GEMINI_API_KEY + special base_url
        self.gemini_client = OpenAI(
            api_key=GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        # OpenAI client uses OPENAI_API_KEY + default endpoint
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def _choose_client(self, model: str) -> OpenAI:
        return (
            self.gemini_client
            if model.lower().startswith("gemini")
            else self.openai_client
        )

    def generate(self, model: str | None = None) -> str:
        model_to_use = model or self.default_model
        client = self._choose_client(model_to_use)
        resp = client.chat.completions.create(
            model=model_to_use,
            messages=self.messages,
            reasoning_effort="medium",
        )
        return resp.choices[0].message.content

    def generate_structured(self, schema, model: str | None = None) -> dict:
        model_to_use = model or self.default_model
        client = self._choose_client(model_to_use)
        resp = client.beta.chat.completions.parse(
            model=model_to_use,
            messages=self.messages,
            reasoning_effort="medium",
            response_format=schema,
        )
        content = resp.choices[0].message.model_dump()["content"]
        return json.loads(content)