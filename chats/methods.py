from chats.models import Chat
from core.ai.chroma import chroma, openai_ef
from core.ai.prompt_manager import PromptManager
from documents.models import Contract


def process_chat(message, contract: Contract, user=None):
    # Insert chat data to database
    Chat.objects.create(message=message, role="user", contract=contract, user=user)

    # Retrieve chromadb collection
    collection = chroma.get_collection(name=contract.id, embedding_function=openai_ef)

    # Find n result of chunks based on user's question
    content = collection.query(
        query_texts=[message],
        n_results=3,
    )

    # Get chat history of user with this contract
    chats = Chat.objects.filter(contract=contract, user=user)

    messages = [
        {
            "role": "system",
            "content": f"You are a helpful assistant. Answer the user's question based on the context provided. Content: {content}, Important: The response should be plain text, no format or table. use double break line for new paragraph",
        }
    ]

    # Add all chat history as context
    for chat in chats:
        messages.append({"role": chat.role, "content": chat.message})

    p = PromptManager()
    p.set_messages(messages)
    res = p.generate()

    # insert the new assistant's answer to database
    Chat.objects.create(
        message=res,
        role="assistant",
        contract=contract,
        user=user,
    )

    return res
