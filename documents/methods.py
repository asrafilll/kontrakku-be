from core.ai.chroma import chroma, openai_ef
from core.ai.mistral import mistral
from core.ai.prompt_manager import PromptManager
from documents.models import CONTRACT_DONE, Contract
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai.embeddings import OpenAIEmbeddings
# from core.methods import send_notification

# def get_chroma_data(contract_id, n_initial_words=10):
#     try:
#         collection = chroma.get_collection(
#             name=contract_id,
#             embedding_function=openai_ef
#         )

#         all_chunks = collection.get(include=["documents"])["documents"]

#         n_chunks = len(all_chunks)
#         initial_snippets = []
#         for chunk in all_chunks:
#             words = chunk.split()
#             snippet = " ".join(words[:n_initial_words])
#             initial_snippets.append(snippet)

#         print(f"Document was split into {n_chunks} chunks.\n")
#         for i, text in enumerate(initial_snippets, start=1):
#             print(f"Chunk {i} starts with: {text!r}")

#     except Exception as e:
#         print(f"Error inspecting chunks: {e}")
#         return 0, []

def process_contract(contract_id):
    # send_notification("notification", "Document processing started")
    contract = Contract.objects.get(id=contract_id)
    file_name = contract.file_path.name

    uploaded_pdf = mistral.files.upload(
        file={
            "file_name": file_name,
            "content": open(f"media/{file_name}", "rb"),
        },
        purpose="ocr",
    )

    signed_url = mistral.files.get_signed_url(file_id=uploaded_pdf.id)

    ocr_response = mistral.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "document_url", "document_url": signed_url.url},
        include_image_base64=False,
    )

    content = ""
    for page in ocr_response.dict().get("pages", []):
        content += page["markdown"]

    pm = PromptManager()
    pm.add_message(
        "system",
        """
        You are a contract summarization assistant.  Your job is:

        <thinking>
        0. Look at the raw contract text and decide whether it is written in English or in Bahasa Indonesia.  
           — If it’s English, set CONTRACT_LANGUAGE = "English".  
           — If it’s Bahasa Indonesia, set CONTRACT_LANGUAGE = "Bahasa Indonesia".  
        1. Carefully review the contract document in that detected language.  
        2. Identify the main purpose, parties involved, and key terms and conditions.  
        3. Determine the appropriate level of detail based on {$SUMMARY_DETAIL_LEVEL}.  
        4. Organize your summary into clear bullet points.  
        5. Make sure your output is in the same language you detected—no switching!  
        </thinking>

        <result>       
        CONTRACT_LANGUAGE: {the language you detected}  
        • [First bullet in that language]  
        • [Second bullet…]  
        </result>
        """
    )
    pm.add_message("user", f"contract: {content}")

    summarized_content = pm.generate()

    contract.raw_text = content
    contract.summarized_text = summarized_content
    contract.status = CONTRACT_DONE
    contract.save()

    splitter = SemanticChunker(OpenAIEmbeddings())
    documents = splitter.create_documents([content])

    collection = chroma.create_collection(name=contract.id, embedding_function=openai_ef)

    chunk_docs = [doc.model_dump().get("page_content") for doc in documents]
    chunk_ids = [str(i) for i in range(len(documents))]

    collection.add(
        documents=chunk_docs,
        ids=chunk_ids
    )

    result_summary = {
        "contract_id": contract.id,
        "file_name": file_name,
        "content_length": len(content),
        "summary_length": len(summarized_content),
        "chunks_created": len(documents),
        "status": contract.status
    }

    return result_summary
