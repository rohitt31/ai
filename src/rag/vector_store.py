"""
Vector store management using ChromaDB.
Handles indexing, persistence, and similarity search with metadata filtering.
Supports both local (free) and OpenAI embeddings.
"""

import chromadb
from chromadb.config import Settings

from src.config import CHROMA_PERSIST_DIR, EMBEDDING_MODEL, OPENAI_API_KEY, EMBEDDING_TYPE
from src.rag.chunker import Chunk

COLLECTION_NAME = "aster_row_kb"


def get_chroma_client() -> chromadb.ClientAPI:
    """Get a persistent ChromaDB client."""
    return chromadb.PersistentClient(
        path=str(CHROMA_PERSIST_DIR),
        settings=Settings(anonymized_telemetry=False),
    )


def get_embedding_function():
    """
    Get the embedding function for ChromaDB.
    Uses local embeddings by default (free, no API key needed).
    Falls back to OpenAI embeddings if configured.
    """
    if EMBEDDING_TYPE == "openai" and OPENAI_API_KEY:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        return OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name=EMBEDDING_MODEL,
        )
    else:
        # Use ChromaDB's default local embedding function
        # Uses all-MiniLM-L6-v2 via onnxruntime — completely free, no API key needed
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        return DefaultEmbeddingFunction()


def build_index(chunks: list[Chunk], force_rebuild: bool = False) -> None:
    """
    Build the ChromaDB index from document chunks.
    If force_rebuild is True, delete and recreate the collection.
    """
    client = get_chroma_client()
    embed_fn = get_embedding_function()
    
    # Check if collection exists and has data
    existing_collections = [c.name for c in client.list_collections()]
    
    if COLLECTION_NAME in existing_collections:
        if not force_rebuild:
            collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embed_fn)
            if collection.count() > 0:
                print(f"Index already exists with {collection.count()} chunks. Use --rebuild to force rebuild.")
                return
        client.delete_collection(name=COLLECTION_NAME)
    
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )
    
    # Prepare data for batch insertion
    ids = []
    documents = []
    metadatas = []
    
    seen_ids = set()
    for chunk in chunks:
        # Ensure unique IDs
        chunk_id = chunk.chunk_id
        counter = 1
        while chunk_id in seen_ids:
            chunk_id = f"{chunk.chunk_id}--{counter}"
            counter += 1
        seen_ids.add(chunk_id)
        
        ids.append(chunk_id)
        documents.append(chunk.content)
        metadatas.append(chunk.to_metadata_dict())
    
    # Batch insert (ChromaDB handles batching internally)
    batch_size = 50
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
        )
    
    print(f"Indexed {len(ids)} chunks into ChromaDB.")


def search(query: str, top_k: int = 5, where_filter: dict | None = None) -> list[dict]:
    """
    Search the vector store for relevant passages.
    Returns list of dicts with content, metadata, and distance score.
    """
    client = get_chroma_client()
    embed_fn = get_embedding_function()
    
    try:
        collection = client.get_collection(name=COLLECTION_NAME, embedding_function=embed_fn)
    except Exception:
        return []
    
    query_params = {
        "query_texts": [query],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    
    if where_filter:
        query_params["where"] = where_filter
    
    results = collection.query(**query_params)
    
    if not results or not results["documents"] or not results["documents"][0]:
        return []
    
    passages = []
    for i, doc in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i] if results["metadatas"] else {}
        distance = results["distances"][0][i] if results["distances"] else 0
        
        passages.append({
            "content": doc,
            "source": metadata.get("source_file", "unknown"),
            "heading": metadata.get("heading", ""),
            "document_title": metadata.get("document_title", ""),
            "document_type": metadata.get("document_type", "unknown"),
            "status": metadata.get("status", "unknown"),
            "audience": metadata.get("audience", "unknown"),
            "effective_date": metadata.get("effective_date", ""),
            "supersedes": metadata.get("supersedes", ""),
            "superseded_by": metadata.get("superseded_by", ""),
            "tags": metadata.get("tags", ""),
            "score": round(1 - distance, 4),  # Convert distance to similarity score
        })
    
    return passages
