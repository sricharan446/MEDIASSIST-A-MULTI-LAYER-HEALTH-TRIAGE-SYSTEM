import os
import chromadb
from sentence_transformers import SentenceTransformer
from rag.document_loader import load_text_from_file

# Embedding model
_model = SentenceTransformer('all-MiniLM-L6-v2')

# ── FIX: Persistent ChromaDB — survives server restarts ───────────────────────
DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
_client = chromadb.PersistentClient(path=DB_PATH)
_collection = _client.get_or_create_collection(name="medical_docs")


def add_document_to_rag(file_path: str) -> str:
    """Load, chunk, embed and store a file. Skips if already indexed."""
    # FIX: Deduplication guard — avoid duplicate-ID crash
    sentinel_id = f"{file_path}::chunk_0"
    existing = _collection.get(ids=[sentinel_id])
    if existing and existing["ids"]:
        return f"Already indexed: {file_path}"

    text = load_text_from_file(file_path)
    if not text or not text.strip():
        return "No readable text found"

    # FIX: Chunk into 1000-char pieces for better retrieval accuracy
    chunks = [text[i:i+1000] for i in range(0, min(len(text), 8000), 1000)]
    if not chunks:
        return "Empty document"

    chunk_ids   = [f"{file_path}::chunk_{i}" for i in range(len(chunks))]
    embeddings  = [_model.encode(chunk).tolist() for chunk in chunks]

    _collection.add(documents=chunks, embeddings=embeddings, ids=chunk_ids)
    return f"Stored {len(chunks)} chunks from {file_path}"


def search_rag(query: str, n_results: int = 2) -> list:
    """Search ChromaDB for most relevant chunks. Returns [] if nothing useful found."""
    try:
        # FIX: Guard against empty collection crash
        count = _collection.count()
        if count == 0:
            return []

        query_embedding = _model.encode(query).tolist()
        results = _collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, count),
            include=["documents", "distances"]
        )

        docs      = results.get("documents", [[]])[0]
        distances = results.get("distances",  [[]])[0]

        # FIX: Relevance threshold — only return docs with distance < 1.2
        # (ChromaDB L2 distance: lower = more similar. 1.2 filters out unrelated docs)
        filtered = [
            doc for doc, dist in zip(docs, distances)
            if dist < 1.2 and doc.strip()
        ]
        return [filtered] if filtered else []

    except Exception as e:
        print(f"RAG search error: {e}")
        return []