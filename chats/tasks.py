from huey.contrib.djhuey import task

from core.methods import send_chat_message

from .methods import process_chat


@task()
def process_chat_task(message, contract_id):
    processed_message = process_chat(message, contract_id)
    print(processed_message)
    send_chat_message(processed_message)
