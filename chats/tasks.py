import json

from huey.contrib.djhuey import task

from chats.models import Chat
from core.ai.chroma import chroma, openai_ef
from core.ai.prompt_manager import PromptManager
from core.methods import send_chat_message

SYSTEM_PROMPT_RAG = """
You are a helpful assistant,
Your task is to answer user question based the provided document

PROVIDED DOCUMENT:
{document}

ANSWER GUIDELINES:
- Always answers in bahasa indonesia
- Do not include any different information other than provided document
"""

SYSTEM_PROMPT_2 = """
You are an expert in the subject matter covered by the provided document: {document}. 
Your task is to answer the user's question based on the information in the document, while adhering to the following guidelines:

1. Answer using the same language as user asked
2. Read the user's question and additional context carefully.
3. Identify the relevant information in the provided document that is necessary to answer the question.
4. Craft a response that directly addresses the user's question, using relevant quotes or paraphrased information from the document.
5. If the user's question cannot be answered solely based on the provided document, politely inform the user that you do not have enough information to provide a complete answer.
6. Do not include any information beyond what is explicitly stated in the document.

<thinking>
[Extract relevant quotes or paraphrased information from the {document} to answer the user's question.]
</thinking>

<result>
[Insert answer based on the extracted information from the document]
</result>
"""


@task()
def process_chat(message, contract_id):
    max_chat_history = 20
    Chat.objects.create(role="user", message=message, contract_id=contract_id)

    collection = chroma.get_collection(contract_id, embedding_function=openai_ef)
    res = collection.query(query_texts=[message], n_results=3)

    messages = []
    chats = Chat.objects.filter(contract_id=contract_id).order_by("created_at")[
        :max_chat_history
    ]

    for chat in chats:
        messages.append({"role": chat.role, "message": chat.message})

    system_prompt = SYSTEM_PROMPT_RAG.format(document=json.dumps(res))

    pm = PromptManager()
    pm.add_message("system", system_prompt)
    for msg in messages:
        pm.add_message(msg["role"], msg["message"])

    assistant_message = pm.generate()

    Chat.objects.create(
        role="assistant", message=assistant_message, contract_id=contract_id
    )
    send_chat_message(assistant_message, contract_id)
