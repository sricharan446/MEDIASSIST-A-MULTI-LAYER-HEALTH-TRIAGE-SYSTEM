import chromadb
from sentence_transformers import SentenceTransformer
from rag.document_loader import load_text_from_file

# embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# chromadb client
client = chromadb.Client()
collection = client.get_or_create_collection(name="documents")


def add_document_to_rag(file_path):
    text = load_text_from_file(file_path)

    if not text.strip():
        return "No readable text found"

    embedding = model.encode(text).tolist()

    collection.add(
        documents=[text],
        embeddings=[embedding],
        ids=[file_path]
    )

    return "Document stored successfully"


def search_rag(query):
    query_embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=2
    )

    return results["documents"]
