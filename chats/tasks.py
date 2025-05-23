import json

from huey.contrib.djhuey import task

from chats.models import Chat
from core.ai.chroma import chroma, openai_ef
from core.ai.prompt_manager import PromptManager
from core.methods import send_chat_message, send_notification

from documents.models import Contract

from documents.preparation import ensure_uu_reference_collection

@task()
def process_chat(message, contract_id):
    max_chat_history = 20

    # 1. Save user input to DB
    Chat.objects.create(role="user", message=message, contract_id=contract_id)
    print("-----1. Created object")

    # 2. Retrieve full contract
    contract = Contract.objects.get(id=contract_id)
    full_contract_text = contract.raw_text
    print("-----2. Retrieved full contract text")

    # # 3. Ensure UU reference collection exists
    uu_collection = ensure_uu_reference_collection()

    # 4. Query ChromaDB for UU references
    # uu_collection = chroma.get_collection(name="uu_reference", embedding_function=openai_ef)
    query_result = uu_collection.query(query_texts=[message], n_results=3)
    reference_chunks = "\n\n---\n\n".join(query_result["documents"][0])
    pasal_numbers = [m["pasal_number"] for m in query_result["metadatas"][0]]
    print("-----3. Retrieved reference chunks")

    # 5. Construct Gemini-style prompt
#     SYSTEM_PROMPT_GEMINI = """
# Kamu adalah asisten hukum berbasis AI.
#
# Jawablah pertanyaan user berdasarkan:
# - Pertanyaan: "{question}"
# - Referensi aturan:\n{references}
# - Isi kontrak penuh:\n{contract}
#
# Jawab dalam bahasa Indonesia. Referensi yang kamu gunakan adalah Undang-Undang No. 13 Tahun 2003 tentang Ketenagakerjaan.
# Jika jawabannya tidak ada dalam Referensi aturan maupun Isi kontrak penuh, katakan dengan sopan jika kamu tidak bisa menjawab.
# """.strip()

    SYSTEM_PROMPT_GEMINI = """
# Prompt Asisten Hukum Ketenagakerjaan

## Identitas dan Peran
Anda adalah asisten hukum AI yang mengkhususkan diri dalam hukum ketenagakerjaan Indonesia. Anda memiliki keahlian dalam menganalisis kontrak kerja dan memberikan interpretasi berdasarkan Undang-Undang No. 13 Tahun 2003 tentang Ketenagakerjaan.

## Input yang Diterima
- **Pertanyaan User**: {question}
- **Referensi Peraturan**: {references}
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
    """.strip()

    system_prompt = SYSTEM_PROMPT_GEMINI.format(
        question=message,
        references=reference_chunks,
        contract=full_contract_text
    )

    # 6. Load message history for conversational context
    messages = []
    chats = Chat.objects.filter(contract_id=contract_id).order_by("created_at")[:max_chat_history]
    for chat in chats:
        messages.append({"role": chat.role, "message": chat.message})

    # 7. Generate assistant response using PromptManager (placeholder for Gemini)
    pm = PromptManager()
    pm.add_message("system", system_prompt)
    for msg in messages:
        pm.add_message(msg["role"], msg["message"])
    print(f"\n\nMessage sent:\n{pm.messages}\n\n")
    assistant_message = pm.generate()
    response = {
        "assistant_message": assistant_message,
        "references_numbers": pasal_numbers
    }

    # 8. Save assistant reply to DB
    Chat.objects.create(role="assistant", message=assistant_message, contract_id=contract_id)

    # 9. Send to frontend
    send_chat_message(response, contract_id)