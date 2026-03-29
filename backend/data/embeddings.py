"""
data/embeddings.py — ChromaDB + sentence-transformers embeddings manager.
Manages vector storage for portfolio context and market data RAG.
"""

import asyncio
from typing import List, Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)

# Lazy global instances
_embedding_model = None
_chroma_client = None
_collections: Dict[str, Any] = {}


def _get_embedding_model():
    """Lazy load sentence-transformers model."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformers model...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded")
    return _embedding_model


def _get_chroma_client():
    """Lazy load ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        import os
        os.makedirs("data/chromadb", exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path="data/chromadb")
        logger.info("ChromaDB client initialized")
    return _chroma_client


def _get_collection(name: str):
    """Get or create a ChromaDB collection."""
    if name not in _collections:
        client = _get_chroma_client()
        _collections[name] = client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
    return _collections[name]


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of embedding vectors.
    """
    model = _get_embedding_model()
    # Use normalize_embeddings parameter for newer sentence-transformers versions
    # Avoid deprecated parameters like convert_to_list
    try:
        embeddings = await asyncio.to_thread(
            model.encode, texts, normalize_embeddings=True
        )
    except TypeError:
        # Fallback for older versions or parameter mismatch
        embeddings = await asyncio.to_thread(model.encode, texts)
    # Normalize output to plain Python lists for Chroma compatibility.
    if hasattr(embeddings, "tolist"):
        return embeddings.tolist()
    return embeddings


async def store_portfolio_context(
    session_id: str,
    documents: List[str],
    metadatas: Optional[List[Dict]] = None,
) -> None:
    """
    Store portfolio documents in ChromaDB under a session namespace.

    Args:
        session_id: Unique session identifier used as collection name.
        documents: List of text passages to store.
        metadatas: Optional metadata dicts for each document.
    """
    collection_name = f"portfolio_{session_id[:36].replace('-', '_')}"
    collection = _get_collection(collection_name)

    embeddings = await embed_texts(documents)

    ids = [f"{session_id}_{i}" for i in range(len(documents))]
    meta = metadatas or [{"source": "portfolio"} for _ in documents]

    await asyncio.to_thread(
        collection.upsert,
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=meta,
    )
    logger.info("Portfolio context stored", session_id=session_id, count=len(documents))


async def retrieve_portfolio_context(
    session_id: str,
    query: str,
    n_results: int = 5,
) -> List[str]:
    """
    Semantic search over a portfolio's stored context.

    Args:
        session_id: Session ID (used to find the collection).
        query: Natural language query.
        n_results: Number of relevant documents to return.

    Returns:
        List of relevant document passages.
    """
    collection_name = f"portfolio_{session_id[:36].replace('-', '_')}"

    try:
        collection = _get_collection(collection_name)
        query_embedding = await embed_texts([query])

        results = await asyncio.to_thread(
            collection.query,
            query_embeddings=query_embedding,
            n_results=min(n_results, collection.count()),
        )

        documents = results.get("documents", [[]])[0]
        logger.info("Context retrieved", session_id=session_id, query=query[:50], count=len(documents))
        return documents

    except Exception as e:
        logger.warning("Context retrieval failed", session_id=session_id, error=str(e))
        return []


async def store_market_signals(signals: List[Dict]) -> None:
    """
    Store market signals in global signals collection for RAG.

    Args:
        signals: List of signal dicts with 'text' and 'metadata' keys.
    """
    collection = _get_collection("market_signals")
    texts = [s.get("text", "") for s in signals]
    metas = [s.get("metadata", {}) for s in signals]
    ids = [s.get("id", f"signal_{i}") for i, s in enumerate(signals)]

    embeddings = await embed_texts(texts)
    await asyncio.to_thread(
        collection.upsert,
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metas,
    )


async def delete_portfolio_context(session_id: str) -> None:
    """Delete all stored context for a session."""
    collection_name = f"portfolio_{session_id[:36].replace('-', '_')}"
    try:
        client = _get_chroma_client()
        await asyncio.to_thread(client.delete_collection, collection_name)
        if collection_name in _collections:
            del _collections[collection_name]
        logger.info("Portfolio context deleted", session_id=session_id)
    except Exception as e:
        logger.warning("Failed to delete collection", session_id=session_id, error=str(e))
