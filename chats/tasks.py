from huey.contrib.djhuey import task
from core.methods import send_chat_message
from core.ai.prompt_manager import PromptManager
from core.ai.chroma import chroma, openai_ef
from chats.models import Chat
# from core.ai.tokenizer import count_token
import json


SYSTEM_PROMPT_RAG = """
You are a helpful assistant,
Your task is to answer user question based the provided document

PROVIDED DOCUMENT:
{document}

ANSWER GUIDELINES:
- Always answers in bahasa indonesia
- Do not include any different information other than provided document
"""
@task()
def process_chat(message, contract_id):
   Chat.objects.create(role="user", message = message, contract_id = contract_id)

   collection = chroma.get_collection(contract_id, embedding_function=openai_ef)
   res = collection.query(query_texts=[message], n_results=3)

   messages=[]
   chats = Chat.objects.filter(contract_id=contract_id).order_by("created_at")[:20]

   for chat in chats:
      messages.append({"role":chat.role, "message":chat.message})

   system_prompt = SYSTEM_PROMPT_RAG.format(document=json.dumps(res))
  #  system_prompt_token = count_token(system_prompt)

   pm = PromptManager()
   pm.add_message("system", system_prompt)
   # pm.add_messages(messages=messages)
   for msg in messages:
    pm.add_message(msg["role"], msg["message"])

  #  messages_token = count_token(json.dumps(messages))

   assistant_message = pm.generate()
  #  assistant_token = count_token(assistant_message)

  #  print(system_prompt_token)
  #  print(messages_token)
  #  print(assistant_token)

   Chat.objects.create(role="assistant", message=assistant_message, contract_id=contract_id)
   send_chat_message(assistant_message, contract_id)