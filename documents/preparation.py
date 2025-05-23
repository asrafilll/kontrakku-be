import re

from core.ai.chroma import chroma, openai_ef

BAB_ROMAN_PATTERN = re.compile(r"^#\s*BAB\s+([IVXLCDM]+)", re.IGNORECASE)
BAB_TITLE_PATTERN = re.compile(r"^##\s*(.+)", re.IGNORECASE)
PASAL_PATTERN = re.compile(r"^###\s*Pasal\s+(\d+)", re.IGNORECASE)
BAGIAN_PATTERN = re.compile(r"^###\s*Bagian\s+(.+)$", re.IGNORECASE)
PARAGRAF_PATTERN = re.compile(r"^####\s*Paragraf\s+(\d+)", re.IGNORECASE)


def parse_uu_document(markdown_text: str):
    """
    Parses the full Undang-Undang text into a list of Pasal chunks,
    with hierarchical metadata (BAB, Bagian, Paragraf).
    Each chunk represents a complete Pasal.
    """
    pasal_chunks = []
    current_bab_romawi = None
    current_bab_judul = None
    current_bagian_judul = None
    current_paragraf_nomor = None

    current_pasal_number = None
    current_pasal_lines = []

    lines = markdown_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[
            i
        ].strip()  # 'line' now holds the stripped content for this iteration

        # Try to match BAB Roman numeral (e.g., # BAB I)
        if bab_roman_match := BAB_ROMAN_PATTERN.match(line):
            # If we were building a Pasal, finalize it
            if current_pasal_number is not None and current_pasal_lines:
                pasal_chunks.append(
                    {
                        "bab_romawi": current_bab_romawi,
                        "bab_judul": current_bab_judul,
                        "bagian_judul": current_bagian_judul,
                        "paragraf_nomor": current_paragraf_nomor,
                        "pasal_number": current_pasal_number,
                        "content": "\n".join(current_pasal_lines).strip(),
                    }
                )
                current_pasal_lines = []
                current_pasal_number = None

            current_bab_romawi = bab_roman_match.group(1)

            # Check the next line for the BAB title (e.g., ## KETENTUAN UMUM)
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if bab_title_match := BAB_TITLE_PATTERN.match(next_line):
                    current_bab_judul = bab_title_match.group(1).strip()
                    i += 1  # Consume the title line
                else:
                    current_bab_judul = None  # No title found on next line

            # Reset Bagian and Paragraf when a new BAB starts
            current_bagian_judul = None
            current_paragraf_nomor = None

        # Check for Bagian heading (e.g., ### Bagian Kesatu)
        elif bagian_match := BAGIAN_PATTERN.match(line):
            # Flush current Pasal if any, before updating Bagian context
            if current_pasal_number is not None and current_pasal_lines:
                pasal_chunks.append(
                    {
                        "bab_romawi": current_bab_romawi,
                        "bab_judul": current_bab_judul,
                        "bagian_judul": current_bagian_judul,
                        "paragraf_nomor": current_paragraf_nomor,
                        "pasal_number": current_pasal_number,
                        "content": "\n".join(current_pasal_lines).strip(),
                    }
                )
                current_pasal_lines = []
                current_pasal_number = None

            current_bagian_judul = bagian_match.group(1).strip()
            # Reset Paragraf when a new Bagian starts
            current_paragraf_nomor = None

        # Check for Paragraf heading (e.g., #### Paragraf 1)
        elif paragraf_match := PARAGRAF_PATTERN.match(line):
            # Flush current Pasal if any, before updating Paragraf context
            if current_pasal_number is not None and current_pasal_lines:
                pasal_chunks.append(
                    {
                        "bab_romawi": current_bab_romawi,
                        "bab_judul": current_bab_judul,
                        "bagian_judul": current_bagian_judul,
                        "paragraf_nomor": current_paragraf_nomor,
                        "pasal_number": current_pasal_number,
                        "content": "\n".join(current_pasal_lines).strip(),
                    }
                )
                current_pasal_lines = []
                current_pasal_number = None

            current_paragraf_nomor = paragraf_match.group(1).strip()

        # Check for Pasal heading (e.g., ### Pasal 1)
        elif pasal_match := PASAL_PATTERN.match(line):
            # If there's an existing Pasal being built, finalize it first
            if current_pasal_number is not None and current_pasal_lines:
                pasal_chunks.append(
                    {
                        "bab_romawi": current_bab_romawi,
                        "bab_judul": current_bab_judul,
                        "bagian_judul": current_bagian_judul,
                        "paragraf_nomor": current_paragraf_nomor,
                        "pasal_number": current_pasal_number,
                        "content": "\n".join(current_pasal_lines).strip(),
                    }
                )
            # Start a new Pasal. The Pasal heading itself is part of the content.
            current_pasal_number = pasal_match.group(1)
            current_pasal_lines = [line]  # Include the Pasal line itself in content

        else:
            # Regular content line, add to current Pasal
            if current_pasal_number is not None:
                current_pasal_lines.append(line)

        i += 1  # Move to the next line

    # Add the very last Pasal chunk after the loop finishes
    if current_pasal_number is not None and current_pasal_lines:
        pasal_chunks.append(
            {
                "bab_romawi": current_bab_romawi,
                "bab_judul": current_bab_judul,
                "bagian_judul": current_bagian_judul,
                "paragraf_nomor": current_paragraf_nomor,
                "pasal_number": current_pasal_number,
                "content": "\n".join(current_pasal_lines).strip(),
            }
        )

    return pasal_chunks


def build_uu_reference_vector_collection(
    input_file_path: str, collection_name: str = "uu_reference"
) -> None:
    """
    Read a UU file (Markdown or PDF), convert to cleaned Markdown,
    split into deterministic Pasal chunks annotated by BAB, Bagian, and Paragraf,
    and ingest into a Chroma collection with embeddings.
    """
    print(f"Loading content from {input_file_path} for processing...")
    with open(input_file_path, "r", encoding="utf-8") as f:
        raw_markdown = f.read()

    cleaned_markdown = re.sub(
        r"\n{3,}", "\n\n", raw_markdown
    )  # replace multilines with two lines
    pasal_chunks = parse_uu_document(cleaned_markdown)

    chunk_ids: list[str] = []
    chunk_texts: list[str] = []
    chunk_metadatas: list[dict] = []

    for idx, pasal_chunk in enumerate(pasal_chunks):
        bab_romawi = pasal_chunk.get("bab_romawi")
        bab_judul = pasal_chunk.get("bab_judul")
        bagian_judul = pasal_chunk.get("bagian_judul")
        paragraf_nomor = pasal_chunk.get("paragraf_nomor")
        pasal_number = pasal_chunk.get("pasal_number")
        content = pasal_chunk.get("content")

        if not content or not pasal_number:
            continue

        cid = "_".join(
            part
            for part in [collection_name, f"BAB{bab_romawi}", f"PASAL{pasal_number}"]
            if part
        )

        # Build the metadata dictionary
        meta = {
            "undang_undang_title": "UNDANG-UNDANG REPUBLIK INDONESIA NOMOR 13 TAHUN 2003 TENTANG KETENAGAKERJAAN",
            "bab_romawi": bab_romawi,
            "bab_judul": bab_judul,
            "pasal_number": pasal_number,
        }

        # Explicitly add bagian_judul and paragraf_nomor only if they exist and are non-empty
        # And ensure they are clean strings.
        if bagian_judul:
            meta["bagian_judul"] = (
                bagian_judul.encode("ascii", "ignore").decode("ascii").strip()
            )
            # If it becomes empty after cleaning, don't include it.
            if not meta["bagian_judul"]:
                del meta["bagian_judul"]

        if paragraf_nomor:
            meta["paragraf_nomor"] = (
                paragraf_nomor.encode("ascii", "ignore").decode("ascii").strip()
            )
            # If it becomes empty after cleaning, don't include it.
            if not meta["paragraf_nomor"]:
                del meta["paragraf_nomor"]

        # Handle cross_references: convert list to string or remove if empty
        cross_references = re.findall(r"Pasal\s+(\d+)", content)
        if cross_references:
            # Sort unique references and join into a single string
            meta["cross_references"] = ",".join(sorted(list(set(cross_references))))
        else:
            # If no cross-references, you can choose to omit the key or set to None
            # Omitting is generally cleaner if the key is not always present.
            pass  # No cross_references key added if the list is empty

        # For other metadata values that are strings, apply cleaning as well
        for key in ["undang_undang_title", "bab_romawi", "bab_judul", "pasal_number"]:
            if key in meta and isinstance(meta[key], str):
                cleaned_value = meta[key].encode("ascii", "ignore").decode("ascii")
                cleaned_value = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned_value)
                meta[key] = cleaned_value.strip()

        chunk_ids.append(cid)
        chunk_texts.append(content)
        chunk_metadatas.append(meta)

    if not chunk_ids:
        print(f"⚠️ No chunks extracted from '{input_file_path}'. Check parsing logic.")
        return

    try:
        chroma.delete_collection(name=collection_name)
        print(f"🗑️ Existing collection '{collection_name}' deleted.")
    except Exception as e:
        print(
            f"⚠️ Could not delete collection '{collection_name}' (maybe it doesn't exist): {e}"
        )

    collection = chroma.create_collection(
        name=collection_name, embedding_function=openai_ef
    )
    print(f"✨ Collection '{collection_name}' re-created.")

    print(f"➕ Adding {len(chunk_ids)} chunks to '{collection_name}'...")
    collection.add(ids=chunk_ids, documents=chunk_texts, metadatas=chunk_metadatas)

    print(f"✅ Collection '{collection_name}' created with {len(chunk_ids)} chunks.")
    print(f"Counted {collection.count()} chunks in the collection.")


def ensure_uu_reference_collection(
    file_path: str = "media/uu_13_2003_gemini.md",
    collection_name: str = "uu_reference",
    force_recreate: bool = False,
):
    """
    Checks if the 'uu_reference' Chroma collection exists. If not, it builds it.
    If force_recreate is True, it will rebuild the collection regardless of its existence.
    """
    if force_recreate:
        print(f"Force recreating collection '{collection_name}'...")
        build_uu_reference_vector_collection(file_path, collection_name)

        collection = chroma.get_collection(
            name=collection_name, embedding_function=openai_ef
        )
        return collection
    else:
        try:
            collection = chroma.get_collection(
                name=collection_name, embedding_function=openai_ef
            )
            print(
                f"🎉 Collection '{collection_name}' found. It contains {collection.count()} items."
            )
            return collection
        except Exception as e:
            print(
                f"Collection '{collection_name}' not found or an error occurred: {e}. Building it now..."
            )
            build_uu_reference_vector_collection(file_path, collection_name)
            collection = chroma.get_collection(
                name=collection_name, embedding_function=openai_ef
            )
            return collection