from huey.contrib.djhuey import task

from core.ai.chroma import chroma, openai_ef
from core.ai.mistral import mistral
from core.ai.prompt_manager import PromptManager
from documents.models import CONTRACT_DONE, Contract
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai.embeddings import OpenAIEmbeddings

@task()
def process_contract(contract: Contract):
    file_name = contract.file_path.name

    #1. Using Mistral AI to process the pdf document into an MD
    uploaded_pdf = mistral.files.upload(
        file={
            "file_name": file_name,
            "content": open(f"media/{file_name}", "rb"),
        },
        purpose="ocr",
    )
    signed_url = mistral.files.get_signed_url(file_id=uploaded_pdf.id)

    print(f"{file_name} - Processing contract")
    ocr_response = mistral.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "document_url", "document_url": signed_url.url},
        include_image_base64=False,
    )

    content = ""
    for page in ocr_response.dict().get("pages", []):
        content += page["markdown"]


    # 2. Summarize the contract
    print(f"{file_name} - Summarizing contract")
    pm = PromptManager()
    pm.add_message(
        "system",
        "Summarize the following contract. And get the bullets point of the content, Only the summarization part is required. DO NOT ADD ANY EXTRA TEXT.",
    )
    pm.add_message("user", f"contract: {content}")

    res = pm.generate()

    # 3. Store contract text and summary
    print(f"{file_name} - Storing contract and summary into database")
    contract.raw_text = content
    contract.summarized_text = res
    contract.status = CONTRACT_DONE
    contract.save()

    # 4. Semantic chunking and embedding
    print(f"{file_name} - Semantic chunking and embedding")
    splitter = SemanticChunker(OpenAIEmbeddings())
    documents = splitter.create_documents([content])

    # 5. Store in ChromaDB
    print(f"{file_name} - Store chunks and embeddings in chroma db")
    collection = chroma.create_collection(name=contract.id, embedding_function=openai_ef)

    collection.add(
        documents=[doc.model_dump().get("page_content") for doc in documents],
        ids=[str(i) for i in range(len(documents))]
    )

    print(f"{file_name} - Contract processing done")