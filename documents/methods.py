import json
import re
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel

from django.utils import timezone
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai.embeddings import OpenAIEmbeddings

from core.ai.chroma import chroma, openai_ef
from core.ai.mistral import mistral
from core.ai.prompt_manager import PromptManager
from core.methods import send_notification
from documents.models import CONTRACT_DONE, Contract

IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def remove_images_from_md(md: str) -> str:
    cleaned = IMAGE_RE.sub("", md)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


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


class SplitResult(BaseModel):
    clauses: list[str]


def detect_title(clause_md: str) -> int | str:
    pm = PromptManager()
    pm.add_message(
        "system",
        "Klasifikasikan pasal berikut ke salah satu dari 12 topik. "
        'Berikan jawaban dalam format satu barus JSON: {"id": <1-12 atau "extra">}.\n'
        + "\n".join(f"{i}. {v['title']}" for i, v in CHECKLIST.items()),
    )
    pm.add_message("user", clause_md)
    try:
        return int(json.loads(pm.generate())["id"])
    except Exception:
        return "extra"


def check_subpoints(clause_md: str, bullets: List[str]) -> List[bool]:
    pm = PromptManager()
    pm.add_message(
        "system",
        "Tentukan apakah pasal berikut *jelas* mencakup tiap sub-poin. "
        "Berikan jawaban berupa JSON array boolean sesuai urutan sub-poin.",
    )
    pm.add_message(
        "user",
        json.dumps(
            {"clause_markdown": clause_md, "subpoints": bullets}, ensure_ascii=False
        ),
    )
    try:
        res = json.loads(pm.generate())
        return [(res[i] if i < len(res) else False) for i in range(len(bullets))]
    except Exception:
        return [False] * len(bullets)


def scan_risk(clause_md: str) -> Dict[str, Any]:
    pm = PromptManager()
    pm.add_message(
        "system",
        "Deteksi risiko yang terdapat pada klausa. Balas JSON: {vague: bool, red_flag: bool, reason: str≤40}",
    )
    pm.add_message("user", clause_md)
    try:
        return json.loads(pm.generate())
    except Exception:
        return {"vague": False, "red_flag": False, "reason": ""}


def summarise_clause(clause_md: str) -> str:
    pm = PromptManager()
    pm.add_message(
        "system",
        "Ringkas pasal kontrak berikut dalam ≤120 kata dalam Bahasa Indonesia.",
    )
    pm.add_message("user", clause_md)
    summary = pm.generate()
    return (summary or "").strip()


def process_contract(contract_id):
    contract = Contract.objects.get(id=contract_id)
    file_name = contract.file_path.name

    # 1. OCR with Mistral
    send_notification("notification", "Processing the contract..")
    print(f"Processing contract ID: {contract.id}")
    # process_contract(contract.id)
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

    # 2. Form a Markdown file
    content = ""
    for page in ocr_response.dict().get("pages", []):
        content += page["markdown"]
    content = remove_images_from_md(content)

    # 3. Split markdown into specific topics
    send_notification("notification", "Understanding the contract..")
    print(f"Understanding the contract ID: {contract.id}")
    splitter = PromptManager()
    splitter.add_message(
        "system",
        (
            "Bagi dokumen kontrak dengan format Markdown berikut menjadi format *JSON* untuk tiap pasal/logical clause. "
            "Berikan jawaban persis satu baris array JSON; setiap elemen berisi satu pasal."
        ),
    )
    splitter.add_message("user", content)
    split_result = splitter.generate_structured(SplitResult)
    clauses: list[str] = split_result.get("clauses", [])
    print("Number of split:", len(clauses))

    # 4) Analysis loops
    coverage_titles = {i: False for i in CHECKLIST}
    coverage_bullets = {i: [False] * len(v["bullets"]) for i, v in CHECKLIST.items()}
    extra_clauses, issues, summaries = [], [], []

    for idx, clause_md in enumerate(clauses, 1):
        print(f"Analyzing clause #{idx}")
        send_notification("notification", f"Analysing clause {idx}/{len(clauses)}…")

        topic_id = detect_title(clause_md)
        if isinstance(topic_id, int):
            coverage_titles[topic_id] = True
            bullet_hits = check_subpoints(clause_md, CHECKLIST[topic_id]["bullets"])
            coverage_bullets[topic_id] = [
                prev or hit
                for prev, hit in zip(coverage_bullets[topic_id], bullet_hits)
            ]
        else:
            extra_clauses.append(idx)

        risk = scan_risk(clause_md)
        if risk["vague"] or risk["red_flag"]:
            issues.append({"clause": idx, **risk})

        summaried_clause = summarise_clause(clause_md)
        print(summaried_clause)
        summaries.append(summaried_clause)

    # 5) Compile report
    missing_titles = [
        CHECKLIST[i]["title"] for i, ok in coverage_titles.items() if not ok
    ]
    missing_bullets: Dict[str, List[str]] = {}
    for i, hits in coverage_bullets.items():
        miss = [bp for bp, ok in zip(CHECKLIST[i]["bullets"], hits) if not ok]
        if miss:
            missing_bullets[CHECKLIST[i]["title"]] = miss

    contract.status = CONTRACT_DONE
    contract.updated_at = timezone.now()
    contract.raw_text = content
    contract.summarized_text = summaries
    contract.save()

    report = {
        "contract_id": str(contract.id),
        "file_name": file_name,
        "present_titles": [
            CHECKLIST[i]["title"] for i, ok in coverage_titles.items() if ok
        ],
        "missing_titles": missing_titles,
        "missing_bullets": missing_bullets,
        "extra_clauses": extra_clauses,
        "issues": issues,
        "summaries": summaries,
    }

    send_notification("notification", f"Analysis of contract {file_name} has been done")
    print(f"Analysis of contract {file_name} has been done")
    print(report)
    return report
