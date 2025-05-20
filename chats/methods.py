from django.contrib.auth.models import User

from chats.models import Chat
from core.ai.chroma import chroma, openai_ef
from core.ai.prompt_manager import PromptManager
from documents.models import Contract



def process_chat(message, contract_id):
    contract = Contract.objects.get(id=contract_id)
    user = User.objects.get(username='admin')
    # Insert chat data to database
    Chat.objects.create(message=message, role="user", contract=contract, user=user)

    # Retrieve chromadb collection
    collection = chroma.get_collection(name=contract_id, embedding_function=openai_ef)

    # Find n result of chunks based on user's question
    content = collection.query(
        query_texts=[message],
        n_results=3,
    )

    # Get chat history of user with this contract
    chats = Chat.objects.filter(contract=contract)

    system_prompt = f"""
    You are a helpful assistant. Answer the user's question based on the context provided. 
    Content: {content}, Important: The response should be plain text, no format or table. 
    Use double break line for new paragraph
    """

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    # Add all chat history as context
    for chat in chats:
        messages.append({"role": chat.role, "content": chat.message})

    p = PromptManager()
    p.set_messages(messages)
    res = p.generate()

    # insert the new assistant's answer to database
    Chat.objects.create(message=res,role="assistant",contract=contract, user=user)

    return res
