"""
RAG module for document-driven retrieval.
"""

from app.rag.embeddings import get_embedding_model, EmbeddingModel
from app.rag.vectorstore import VectorStoreManager, ClientVectorStore, DocumentChunk, RetrievalResult
from app.rag.ingest import DocumentIngester, ingest_client_documents, ingest_all_clients
from app.rag.retriever import DocumentRetriever, RetrievalResponse, retrieve_for_client

__all__ = [
    "get_embedding_model",
    "EmbeddingModel",
    "VectorStoreManager",
    "ClientVectorStore",
    "DocumentChunk",
    "RetrievalResult",
    "DocumentIngester",
    "ingest_client_documents",
    "ingest_all_clients",
    "DocumentRetriever",
    "RetrievalResponse",
    "retrieve_for_client",
]
