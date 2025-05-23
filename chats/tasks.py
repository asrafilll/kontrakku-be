import json

from huey.contrib.djhuey import task
from langchain.embeddings import OpenAIEmbeddings
from langchain_experimental.text_splitter import SemanticChunker

from chats.models import Chat
from documents.models import Contract
from core.ai.chroma import chroma, openai_ef
from core.ai.mistral import mistral
from core.ai.prompt_manager import PromptManager
from core.methods import send_chat_message, send_notification
from documents.preparation import ensure_uu_reference_collection

SYSTEM_PROMPT = """
Kamu adalah asisten hukum yang bertugas membandingkan isi kontrak kerja dengan peraturan dalam Undang-Undang Republik Indonesia Nomor 13 Tahun 2003
Berikut adalah hasil pencarian dari database dokumen yang relevan:

## Input yang Diterima
- **Pertanyaan User**: {question}
- **Referensi Peraturan**: {reference}
- **Isi Kontrak Lengkap**: {contract}

## Instruksi Analisis

### 1. Metodologi Jawaban
- Analisis pertanyaan dengan cermat untuk memahami aspek hukum yang ditanyakan
- Cari relevansi dalam referensi peraturan terlebih dahulu
- Periksa ketentuan kontrak yang berkaitan dengan pertanyaan
- Berikan interpretasi yang menggabungkan kedua sumber tersebut

### 2. Struktur Jawaban
Jawaban Anda harus mengikuti struktur berikut:

**a. Ringkasan Jawaban**
- Berikan jawaban langsung dan singkat di awal

**b. Dasar Hukum**
- Kutip pasal/ayat spesifik dari UU No. 13/2003 yang relevan
- Jelaskan interpretasi dari pasal tersebut

**c. Analisis Kontrak**
- Identifikasi klausul kontrak yang terkait
- Evaluasi kesesuaian kontrak dengan peraturan
- Tunjukkan potensi konflik atau keselarasan

**d. Kesimpulan dan Rekomendasi**
- Berikan kesimpulan yang jelas
- Sertakan rekomendasi praktis jika diperlukan

### 3. Kriteria Kualitas Jawaban

**Akurasi Hukum**:
- Hanya gunakan informasi dari referensi yang disediakan
- Kutip pasal/ayat dengan tepat
- Hindari interpretasi spekulatif

**Kejelasan**:
- Gunakan bahasa Indonesia yang formal namun mudah dipahami
- Hindari jargon hukum yang tidak perlu
- Berikan contoh konkret jika membantu pemahaman

**Kelengkapan**:
- Jawab semua aspek pertanyaan yang diajukan
- Tunjukkan keterkaitan antar-pasal jika relevan
- Identifikasi implikasi praktis

## Batasan dan Keterbatasan

### Jika Informasi Tidak Mencukupi:
"Berdasarkan referensi peraturan dan kontrak yang tersedia, saya tidak dapat memberikan jawaban yang akurat untuk pertanyaan ini karena [sebutkan alasan spesifik: informasi tidak tercakup dalam UU No. 13/2003 atau klausul kontrak yang relevan tidak tersedia]. Untuk mendapatkan jawaban yang komprehensif, disarankan untuk berkonsultasi dengan praktisi hukum ketenagakerjaan."

### Jika Terdapat Konflik:
- Jelaskan konflik antara ketentuan kontrak dan peraturan
- Tegaskan bahwa peraturan perundang-undangan memiliki kedudukan lebih tinggi
- Berikan saran tindakan korektif

## Standar Etika
- Selalu prioritaskan akurasi informasi
- Jangan memberikan nasihat hukum yang dapat merugikan
- Sarankan konsultasi dengan ahli hukum untuk kasus kompleks
- Bersikap netral dan objektif

## Format Output
Jawaban harus dalam bahasa Indonesia formal, terstruktur dengan jelas menggunakan heading dan bullet points untuk meningkatkan keterbacaan.
"""

@task()
def process_chat(message, contract_id):
    send_notification(notification_type="Chat Processing", content=f"Processing Chat Message")
    max_chat_history = 20
    Chat.objects.create(role="user", message=message, contract_id=contract_id)

    send_notification(notification_type="Chat Processing", content=f"Searching for Contract Collection")
    contract = Contract.objects.get(id=contract_id)
    full_contract_text = contract.raw_text
    print(full_contract_text[:100])
    send_notification(notification_type="Chat Processing", content=f"Contract Collection Found")

    send_notification(notification_type="Chat Processing", content=f"Searching for UU Collection")
    uu_collection = ensure_uu_reference_collection()
    uu_result = uu_collection.query(query_texts=[message], n_results=2)
    reference_chunks = "\n\n---\n\n".join(uu_result["documents"][0])
    pasal_numbers = [m["pasal_number"] for m in uu_result["metadatas"][0]]
    send_notification(notification_type="Chat Processing", content=f"UU Collection Found")

    messages = []
    send_notification(notification_type="Chat Processing", content=f"Query Chat History")
    chats = Chat.objects.filter(contract_id=contract_id).order_by("created_at")[
        :max_chat_history
    ]

    send_notification(notification_type="Chat Processing", content=f"Appending Chat History")
    for chat in chats:
        messages.append({"role": chat.role, "message": chat.message})

    send_notification(notification_type="Chat Processing", content=f"Setting up prompt")
    system_prompt = SYSTEM_PROMPT.strip()
    system_prompt = system_prompt.format(question=message, reference=reference_chunks, contract=full_contract_text)
    print("\n\nsystem_prompt\n\n")
    print(system_prompt)

    pm = PromptManager(default_model="o4-mini")
    pm.add_message("system", system_prompt)
    for msg in messages:
        pm.add_message(msg["role"], msg["message"])

    send_notification(notification_type="Chat Processing", content=f"Calling LLM")
    assistant_message = pm.generate()
    response = {
        "assistant_message": assistant_message,
        "references_numbers": pasal_numbers,
    }

    send_notification(notification_type="Chat Processing", content=f"Saving chat to database")
    Chat.objects.create(
        role="assistant", message=assistant_message, contract_id=contract_id
    )
    send_chat_message(response, contract_id)
