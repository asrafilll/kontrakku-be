import json
import re
from typing import Any, Dict, List, Union

from django.utils import timezone
from pydantic import BaseModel, Field, ValidationError

from core.ai.mistral import mistral
from core.ai.prompt_manager import PromptManager
from core.methods import send_chat_message, send_notification
from documents.models import CONTRACT_DONE, Contract

IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def remove_images_from_md(md: str) -> str:
    cleaned = IMAGE_RE.sub("", md)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


class SplitResult(BaseModel):
    clauses: list[str] = Field(
        ..., description="A list of contract clauses, each as a string."
    )


class SubpointCoverageResult(BaseModel):
    coverage: List[bool] = Field(
        ...,
        description="Boolean flags indicating coverage for each sub-point in order.",
    )


class ClauseAnalysisResult(BaseModel):
    """Pydantic model for the combined analysis result of a single clause."""

    topic_id: int | str = Field(
        ...,
        description="The ID of the category from CHECKLIST, or 'extra' if no match.",
    )
    summary: str = Field(
        ...,
        description="A simple explanation/summary of the contract clause in <=120 words.",
    )
    vague: bool = Field(..., description="True if the clause is vague.")
    red_flag: bool = Field(
        ..., description="True if the clause contains a red flag/risk."
    )
    risk_reason: str = Field(
        ...,
        description="A concise reason (<=40 words) why the clause is vague or a red flag, if applicable.",
    )
    questions_for_company: List[str] = Field(
        ...,
        description="A list of specific questions to ask the company regarding this clause, if needed.",
    )


def check_subpoints(clause_md: str, bullets: List[str]) -> List[bool]:
    """
    Determines which sub-points are clearly covered in the clause
    by asking the LLM to return a JSON object with a `coverage` list.
    """
    pm = PromptManager()
    pm.add_message(
        "system",
        (
            "Tentukan apakah pasal berikut *jelas* mencakup tiap sub-poin.\n"
            "Balas dengan JSON berisi field `coverage`, berupa array boolean\n"
            "sesuai urutan sub-poin. Contoh:\n"
            '{"coverage": [true, false, true]}\n'
            "Pastikan JSON valid."
        ),
    )
    pm.add_message(
        "user",
        json.dumps(
            {"clause_markdown": clause_md, "subpoints": bullets}, ensure_ascii=False
        ),
    )

    try:
        raw: Union[dict, str] = pm.generate_structured(SubpointCoverageResult)

        # parse into our Pydantic model
        if isinstance(raw, str):
            result = SubpointCoverageResult.model_validate_json(raw)
        else:
            result = SubpointCoverageResult.model_validate(raw)

        # pad/trim to match number of bullets
        cov = result.coverage
        return [cov[i] if i < len(cov) else False for i in range(len(bullets))]

    except (ValidationError, json.JSONDecodeError, Exception) as e:
        print(f"Error checking subpoints with LLM: {e}")
        return [False] * len(bullets)


def process_single_clause_with_llm(clause_md: str) -> ClauseAnalysisResult:
    """
    Performs a combined analysis of a single contract clause using one LLM call.
    This includes topic categorization, summarization, risk detection, and question generation.
    """
    pm = PromptManager()
    topic_list_str = "\n    ".join(f"{i}. {v['title']}" for i, v in CHECKLIST.items())
    pm.add_message(
        "system",
        (
            "Anda adalah asisten analisis kontrak yang cerdas dan efisien. "
            "Untuk setiap klausa yang diberikan, Anda harus melakukan analisis lengkap dalam satu respons JSON. "
            "Ikuti instruksi di bawah ini dengan cermat dan berikan output dalam format JSON yang telah ditentukan.\n\n"
            "**Instruksi Analisis Klausa:**\n"
            "1.  **Kategorisasi Topik**: Klasifikasikan klausa ke salah satu topik berikut. Jika tidak ada yang cocok, gunakan 'extra'.\n"
            f"    {topic_list_str}\n"
            "2.  **Ringkasan Sederhana**: Ringkas klausa dalam Bahasa Indonesia menjadi maksimal 120 kata.\n"
            "3.  **Deteksi Risiko**: Identifikasi apakah klausa tersebut 'vague' (ambigu) atau 'red_flag' (berisiko tinggi). Berikan alasan singkat (maksimal 40 kata) jika ya. Jika tidak ada risiko, biarkan alasan kosong.\n"
            "4.  **Pertanyaan untuk Perusahaan**: Buat daftar pertanyaan spesifik yang perlu diajukan kepada perusahaan terkait klausa ini untuk klarifikasi atau mitigasi risiko. Jika tidak ada pertanyaan, berikan daftar kosong.\n\n"
            "**Format Output JSON yang Diinginkan:**\n"
            "```json\n"
            "{\n"
            '  "topic_id": <int | "extra">, \n'
            '  "summary": "<ringkasan klausa>",\n'
            '  "vague": <true | false>,\n'
            '  "red_flag": <true | false>,\n'
            '  "risk_reason": "<alasan jika vague/red_flag, maks 40 kata>",\n'
            '  "questions_for_company": ["<pertanyaan 1>", "<pertanyaan 2>"]\n'
            "}\n"
            "```\n"
            "Pastikan Anda selalu menghasilkan JSON yang valid dan lengkap sesuai skema yang diminta."
        ),
    )
    pm.add_message("user", clause_md)

    try:
        raw = pm.generate_structured(ClauseAnalysisResult)
        if isinstance(raw, str):
            return ClauseAnalysisResult.model_validate_json(raw)
        else:
            return ClauseAnalysisResult.model_validate(raw)
    except Exception as e:
        print(f"Error processing clause with LLM: {e}")
        # Return a default/empty result on error
        return ClauseAnalysisResult(
            topic_id="extra",
            summary="Tidak dapat menganalisis klausa ini karena kesalahan LLM.",
            vague=False,
            red_flag=False,
            risk_reason=f"Error: {e}",
            questions_for_company=[
                "Ada masalah saat menganalisis klausa ini. Perlu ditinjau manual."
            ],
        )


CHECKLIST: Dict[int, Dict[str, Any]] = {
    1: {
        "title": "Pekerjaan & Status Kepegawaian",
        "bullets": [
            "Judul & Deskripsi Pekerjaan: Pastikan jabatan dan tugas utama jelas, termasuk 'other duties as assigned'.",
            "Jenis Kontrak: Pahami perbedaan PKWT (Perjanjian Kerja Waktu Tertentu) dan PKWTT (Perjanjian Kerja Waktu Tidak Tertentu).",
            "Catatan PKWT: Hanya untuk pekerjaan non-permanen, maksimal 2 tahun dan dapat diperpanjang 1 kali selama 1 tahun. Jika tidak tertulis atau syaratnya tidak dipenuhi, secara hukum menjadi PKWTT.",
            "Status Kepegawaian: Pastikan status karyawan (tetap, kontrak, magang) dan hak/kewajibannya terkait.",
        ],
    },
    2: {
        "title": "Kompensasi & Tunjangan",
        "bullets": [
            "Gaji Pokok: Perhatikan besaran gaji dan pastikan tidak di bawah upah minimum yang berlaku (provinsi/kabupaten/kota/sektoral).",
            "Komponen Upah: Jika ada tunjangan tetap, pastikan upah pokok minimal 75% dari total upah pokok dan tunjangan tetap.",
            "Gaji Saat Tidak Bekerja: Pahami kondisi di mana upah tetap dibayar meskipun tidak bekerja (misalnya sakit, cuti haid, menikah, ibadah).",
            "THR & Tunjangan Lain: Pastikan jadwal dan formula perhitungan THR serta tunjangan lain yang berlaku.",
            "Bonus & Insentif: Pahami kriteria, target, dan frekuensi pembayaran bonus/insentif.",
        ],
    },
    3: {
        "title": "Jam Kerja, Lembur & Cuti",
        "bullets": [
            "Jam Kerja: Pastikan jam kerja sesuai ketentuan (7 jam/hari, 40 jam/minggu untuk 6 hari kerja; atau 8 jam/hari, 40 jam/minggu untuk 5 hari kerja).",
            "Lembur: Pahami syarat, tarif, dan batasan jam lembur (maksimal 3 jam/hari, 14 jam/minggu) serta kewajiban pembayaran upah lembur.",
            "Cuti: Pastikan hak cuti tahunan (minimal 12 hari kerja setelah 12 bulan terus menerus), istirahat mingguan, istirahat panjang, dan cuti khusus lainnya seperti cuti melahirkan/keguguran dan cuti haid.",
            "Hari Libur: Pahami hak tidak wajib bekerja pada hari libur resmi dan ketentuan upah lembur jika bekerja pada hari tersebut.",
        ],
    },
    4: {
        "title": "Masa Percobaan (Probation)",
        "bullets": [
            "Durasi: Untuk PKWTT, masa percobaan maksimal 3 bulan. Untuk PKWT, masa percobaan dilarang dan batal demi hukum.",
            "Ketentuan Gaji: Selama masa percobaan, upah tidak boleh di bawah upah minimum.",
        ],
    },
    5: {
        "title": "Durasi Kontrak & Pengakhiran",
        "bullets": [
            "Tanggal Mulai & Berakhir: Perhatikan tanggal mulai dan berakhirnya kontrak.",
            "Pengakhiran Hubungan Kerja: Pahami kondisi yang dapat mengakhiri hubungan kerja (misalnya meninggalnya pekerja, berakhirnya jangka waktu kontrak, atau putusan pengadilan).",
            "Perpindahan Perusahaan: Hubungan kerja tidak berakhir jika pengusaha meninggal atau perusahaan dialihkan; hak pekerja menjadi tanggung jawab pengusaha baru.",
        ],
    },
    6: {
        "title": "Peraturan Resign & PHK",
        "bullets": [
            "Upaya Pencegahan PHK: Pahami bahwa PHK harus diupayakan sebagai jalan terakhir dan wajib dirundingkan.",
            "Alasan Larangan PHK: Perhatikan alasan-alasan PHK yang dilarang (misalnya sakit, hamil, membentuk serikat pekerja, perbedaan SARA); PHK berdasarkan alasan ini batal demi hukum dan pekerja wajib dipekerjakan kembali.",
            "Hak Pesangon & Uang Penghargaan: Pahami perhitungan uang pesangon, uang penghargaan masa kerja, dan uang penggantian hak sesuai masa kerja dan alasan PHK.",
            "PHK untuk Kesalahan Berat: Pahami jenis-jenis kesalahan berat yang dapat menyebabkan PHK, persyaratan bukti, dan hak yang diterima pekerja (hanya uang penggantian hak dan uang pisah).",
            "Pengunduran Diri: Pahami prosedur pengunduran diri yang benar agar tidak kehilangan hak (pemberitahuan 30 hari, tidak terikat ikatan dinas, tetap bekerja hingga tanggal mundur).",
            "PHK karena Kondisi Perusahaan: Pahami hak-hak dalam kasus PHK karena perusahaan tutup, efisiensi, pailit, atau perubahan status/merger/akuisisi.",
            "PHK karena Usia Pensiun: Pahami hak-hak pensiun dan bagaimana perhitungannya terkait dengan uang pesangon dan uang penghargaan masa kerja.",
            "PHK karena Mangkir: Pahami syarat dan konsekuensi PHK karena mangkir (5 hari kerja berturut-turut tanpa keterangan sah dan sudah dipanggil).",
        ],
    },
    7: {
        "title": "Kerahasiaan & Kekayaan Intelektual",
        "bullets": [
            "Confidentiality: Pahami informasi apa yang dianggap rahasia perusahaan dan kewajiban menjaganya.",
            "IP Assignment: Pastikan siapa yang memiliki hak cipta/paten atas hasil kerja Anda.",
        ],
    },
    8: {
        "title": "Pembatasan & Non-Compete",
        "bullets": [
            "Non-Compete: Perhatikan jika ada klausul pembatasan pekerjaan setelah keluar dari perusahaan (wilayah, durasi, jenis usaha).",
            "Non-Solicit / Non-Poach: Pahami batasan untuk mengajak karyawan atau klien lama.",
        ],
    },
    9: {
        "title": "Kesehatan & Keselamatan Kerja",
        "bullets": [
            "Hak Perlindungan: Pekerja berhak atas perlindungan keselamatan dan kesehatan kerja, moral, kesusilaan, serta perlakuan manusiawi.",
            "Sistem Manajemen K3: Perusahaan wajib menerapkan sistem manajemen K3.",
            "Perlindungan Khusus: Perhatikan perlindungan untuk penyandang cacat, pembatasan kerja anak (termasuk jenis pekerjaan terburuk), dan perlindungan khusus untuk pekerja perempuan (jam malam, hamil, menyusui).",
        ],
    },
    10: {
        "title": "Jaminan Sosial & Kesejahteraan",
        "bullets": [
            "Jaminan Sosial Tenaga Kerja: Pekerja dan keluarga berhak atas jaminan sosial tenaga kerja.",
            "Fasilitas Kesejahteraan: Perusahaan wajib menyediakan fasilitas kesejahteraan sesuai kebutuhan pekerja dan kemampuan perusahaan.",
            "Koperasi Pekerja/Buruh: Pahami adanya pembentukan koperasi dan usaha produktif untuk kesejahteraan pekerja.",
        ],
    },
    11: {
        "title": "Peraturan Perusahaan & Perjanjian Kerja Bersama (PKB)",
        "bullets": [
            "Peraturan Perusahaan: Perusahaan dengan minimal 10 pekerja wajib memiliki peraturan perusahaan yang disahkan, kecuali sudah ada PKB. Peraturan ini tidak boleh bertentangan dengan undang-undang dan berlaku maksimal 2 tahun.",
            "Perjanjian Kerja Bersama (PKB): PKB dibuat oleh serikat pekerja/buruh dan pengusaha, berlaku maksimal 2 tahun, dan tidak boleh bertentangan dengan undang-undang. PKB mengikat perjanjian kerja individual.",
            "Hierarki: Ketentuan dalam peraturan perusahaan atau PKB tidak boleh lebih rendah dari peraturan perundang-undangan.",
        ],
    },
    12: {
        "title": "Penyelesaian Sengketa",
        "bullets": [
            "Prioritas Musyawarah: Perselisihan hubungan industrial wajib diselesaikan secara musyawarah mufakat terlebih dahulu.",
            "Mogok Kerja: Pahami hak mogok kerja sebagai akibat gagalnya perundingan, dengan prosedur pemberitahuan dan larangan pengusaha mengganti pekerja yang mogok atau memberikan sanksi.",
            "Penutupan Perusahaan (Lock-out): Pahami hak pengusaha untuk melakukan lock-out akibat gagalnya perundingan, dengan batasan dan larangan di sektor vital.",
            "Proses Hukum: Jika musyawarah gagal, penyelesaian melalui prosedur penyelesaian perselisihan hubungan industrial (mediasi, konsiliasi, arbitrase, pengadilan).",
        ],
    },
    13: {
        "title": "Sanksi & Administratif",
        "bullets": [
            "Sanksi Pidana: Pelanggaran terhadap ketentuan krusial dalam undang-undang (misalnya mempekerjakan anak di pekerjaan terburuk, tidak membayar upah minimum, atau PHK yang dilarang) dapat dikenakan sanksi pidana penjara dan/atau denda.",
            "Sanksi Administratif: Pelanggaran terhadap ketentuan lainnya dapat dikenakan sanksi administratif oleh Menteri atau pejabat yang ditunjuk (teguran, peringatan, pembekuan usaha, pencabutan izin).",
            "Kewajiban Pembayaran Hak: Sanksi pidana dan administratif tidak menghilangkan kewajiban pengusaha untuk tetap membayar hak-hak pekerja.",
        ],
    },
    14: {
        "title": "Klausa Lain-lain",
        "bullets": [
            "Amendemen: Pahami bagaimana kontrak dapat diubah dan oleh siapa.",
            "Assignment: Ketahui apakah perusahaan dapat memindahkan kontrak Anda ke entitas lain.",
            "Entire Agreement & Severability: Klausul standar yang menyatakan kontrak adalah keseluruhan perjanjian dan jika ada satu bagian yang tidak sah, tidak membatalkan seluruh kontrak.",
        ],
    },
}

TITLE_MAP = {v["title"].lower(): k for k, v in CHECKLIST.items()}


def process_contract(contract_id):
    contract = Contract.objects.get(id=contract_id)
    file_name = contract.file_path.name

    # 1. OCR upload & processing
    send_notification(
        notification_type="Document Processing", content=f"Membaca dokumen"
    )
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
    print("Done OCR")

    # 2. Compose Markdown
    content = ""
    for page in ocr_response.model_dump().get("pages", []):
        content += page.get("markdown", "")
    content = remove_images_from_md(content)

    # 3. Split Markdown into clauses
    send_notification(
        notification_type="Document Processing", content=f"Memecah dokumen per klausa"
    )
    splitter = PromptManager()
    splitter.add_message(
        "system",
        (
            "Bagi dokumen kontrak dalam format Markdown menjadi JSON array klausa. "
            "Setiap elemen adalah satu pasal/klausa sebagai string."
        ),
    )
    splitter.add_message("user", content)
    split_result = splitter.generate_structured(SplitResult)
    clauses: list[str] = split_result.get("clauses", [])
    print("Number of split:", len(clauses))
    for clause in clauses:
        print(clause[:20])
    print()

    send_notification(
        notification_type="Document Processing",
        content=f"Dokumen dipecah sebanyak {len(clauses)} bagian",
    )

    # 4. Analyze each clause
    send_notification(
        notification_type="Document Processing",
        content=f"Menganalisa dokumen per bagian",
    )
    coverage_titles = {i: False for i in CHECKLIST}
    summaries: list[str] = []
    report_clauses: list[dict] = []

    for idx, clause_md in enumerate(clauses, 1):
        send_notification(
            notification_type="Document Processing",
            content=f"Memeriksa bagian - {idx}/{len(clauses)}",
        )
        print(f"\n\nAnalyzing clause #{idx}")
        analysis = process_single_clause_with_llm(clause_md)

        # # track covered topics
        # tid = analysis.topic_id
        # if isinstance(tid, int) and tid in CHECKLIST:
        #     coverage_titles[tid] = True

        # resolve the topic name -----------------------------▼
        if isinstance(analysis.topic_id, int) and analysis.topic_id in CHECKLIST:
            topic_name = CHECKLIST[analysis.topic_id]["title"]
            coverage_titles[analysis.topic_id] = True  # keep coverage logic
        else:
            topic_name = "extra"

        # collect summary
        summaries.append(analysis.summary)

        # build clause entry
        report_clauses.append(
            {
                # "clauseTopic": analysis.topic_id,
                "clauseTopic": topic_name,
                "clauseContent": clause_md,
                "clauseSummary": analysis.summary,
                "vague": analysis.vague,
                "redFlag": analysis.red_flag,
                "issueReason": analysis.risk_reason,
                "questions": analysis.questions_for_company,
            }
        )

    # 5. Contract-level summary
    send_notification(
        notification_type="Document Processing", content=f"Meringkas isi dari kontrak"
    )
    pm_summary = PromptManager()
    pm_summary.add_message(
        "system",
        "Dari ringkasan pasal di atas, buat ringkasan keseluruhan kontrak dalam Bahasa Indonesia.",
    )
    pm_summary.add_message("user", "\n\n".join(summaries))
    contract_summary = pm_summary.generate()

    # 6. Build simplified report
    covered = [CHECKLIST[i]["title"] for i, ok in coverage_titles.items() if ok]
    uncovered = [CHECKLIST[i]["title"] for i, ok in coverage_titles.items() if not ok]

    report = {
        "fileName": file_name,
        "contractSummary": contract_summary,
        "coveredTopic": covered,
        "uncoveredTopic": uncovered,
        "clauses": report_clauses,
    }

    # validate json
    pretty_json = json.dumps(report, ensure_ascii=False, indent=2, default=str)

    contract.raw_text = content
    contract.summarized_text = pretty_json
    contract.status = CONTRACT_DONE
    contract.updated_at = timezone.now()
    contract.save()

    send_notification(
        notification_type="Document Processing", content=f"Pemrosesan selesai"
    )
    send_notification(notification_type="Processing Done", content=report)

    return report
