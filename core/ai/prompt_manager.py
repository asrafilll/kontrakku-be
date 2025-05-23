import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
client = OpenAI(
    api_key=API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",  # for Gemini
)


class PromptManager:
    def __init__(self, messages=[], model="gemini-2.5-flash-preview-05-20"):
        self.messages = messages
        self.model = model

    def add_message(self, role, content):
        self.messages.append({"role": role, "content": content})

    def set_messages(self, messages):
        self.messages = messages

    def get_messages(self):
        return self.messages

    def generate(self):
        response = client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            reasoning_effort="medium",
        )
        return response.choices[0].message.content

    def generate_structured(self, schema):
        response = client.beta.chat.completions.parse(
            model=self.model,
            messages=self.messages,
            reasoning_effort="medium",
            response_format=schema,
        )

        result = response.choices[0].message.model_dump()
        content = json.loads(result["content"])
        return content
