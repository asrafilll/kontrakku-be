from core.ai.chroma import chroma, openai_ef

def get_chroma(contract_id, n_initial_words=10):
    try:
        collection = chroma.get_collection(
            name=contract_id,
            embedding_function=openai_ef
        )

        all_chunks = collection.get(include=["documents"])["documents"]

        n_chunks = len(all_chunks)
        initial_snippets = []
        for chunk in all_chunks:
            words = chunk.split()
            snippet = " ".join(words[:n_initial_words])
            initial_snippets.append(snippet)

        print(f"Document was split into {n_chunks} chunks.\n")
        for i, text in enumerate(initial_snippets, start=1):
            print(f"Chunk {i} starts with: {text!r}")

    except Exception as e:
        print(f"Error inspecting chunks: {e}")
        return 0, []
