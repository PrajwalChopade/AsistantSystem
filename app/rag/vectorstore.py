"""
FAISS-based vector store with per-client persistence.
"""

import os
import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import threading
import hashlib

from app.config import settings
from app.rag.embeddings import get_embedding_model


@dataclass
class DocumentChunk:
    """A chunk of document with metadata."""
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[np.ndarray] = None


@dataclass  
class RetrievalResult:
    """Result from vector search."""
    content: str
    score: float
    metadata: Dict[str, Any]


class ClientVectorStore:
    """Per-client FAISS vector store with persistence."""
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.store_dir = settings.VECTORSTORE_DIR / client_id
        self.index_path = self.store_dir / "faiss.index"
        self.chunks_path = self.store_dir / "chunks.pkl"
        self.version_path = self.store_dir / "version.txt"
        
        self.index: Optional[faiss.Index] = None
        self.chunks: List[DocumentChunk] = []
        self.version: str = ""
        self._lock = threading.Lock()
        
        self._load_or_create()
    
    def _load_or_create(self):
        """Load existing index or create new one."""
        self.store_dir.mkdir(parents=True, exist_ok=True)
        
        if self.index_path.exists() and self.chunks_path.exists():
            self._load()
        else:
            self._create_empty()
    
    def _create_empty(self):
        """Create empty FAISS index."""
        self.index = faiss.IndexFlatIP(settings.EMBEDDING_DIMENSION)
        self.chunks = []
        self.version = self._generate_version()
    
    def _load(self):
        """Load index and chunks from disk."""
        try:
            self.index = faiss.read_index(str(self.index_path))
            with open(self.chunks_path, "rb") as f:
                self.chunks = pickle.load(f)
            if self.version_path.exists():
                self.version = self.version_path.read_text().strip()
            else:
                self.version = self._generate_version()
            print(f"✅ Loaded vector store for client: {self.client_id} ({len(self.chunks)} chunks)")
        except Exception as e:
            print(f"⚠️ Failed to load vector store for {self.client_id}: {e}")
            self._create_empty()
    
    def _save(self):
        """Persist index and chunks to disk."""
        try:
            faiss.write_index(self.index, str(self.index_path))
            with open(self.chunks_path, "wb") as f:
                pickle.dump(self.chunks, f)
            self.version_path.write_text(self.version)
            print(f"💾 Saved vector store for client: {self.client_id}")
        except Exception as e:
            print(f"❌ Failed to save vector store for {self.client_id}: {e}")
            raise
    
    def _generate_version(self) -> str:
        """Generate version hash based on content."""
        import time
        return hashlib.md5(f"{self.client_id}_{time.time()}".encode()).hexdigest()[:8]
    
    def add_chunks(self, chunks: List[DocumentChunk]):
        """Add document chunks to the store."""
        if not chunks:
            return
            
        with self._lock:
            embedding_model = get_embedding_model()
            
            # Embed all chunks
            texts = [c.content for c in chunks]
            embeddings = embedding_model.embed_documents(texts)
            
            # Add to FAISS index
            self.index.add(embeddings)
            
            # Store chunks with embeddings
            for chunk, emb in zip(chunks, embeddings):
                chunk.embedding = emb
                self.chunks.append(chunk)
            
            # Update version and persist
            self.version = self._generate_version()
            self._save()
    
    def search(
        self, 
        query: str, 
        top_k: int = None,
        min_score: float = None
    ) -> List[RetrievalResult]:
        """
        Search for similar documents.
        
        Args:
            query: Search query
            top_k: Number of results (default from settings)
            min_score: Minimum similarity score (default from settings)
            
        Returns:
            List of RetrievalResult sorted by score descending
        """
        if self.index.ntotal == 0:
            return []
        
        top_k = top_k or settings.RETRIEVAL_TOP_K
        min_score = min_score if min_score is not None else settings.SIMILARITY_THRESHOLD
        
        embedding_model = get_embedding_model()
        query_vec = embedding_model.embed_query(query).reshape(1, -1)
        
        # Search FAISS
        scores, indices = self.index.search(query_vec, min(top_k, self.index.ntotal))
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or score < min_score:
                continue
            chunk = self.chunks[idx]
            results.append(RetrievalResult(
                content=chunk.content,
                score=float(score),
                metadata=chunk.metadata
            ))
        
        return results
    
    def clear(self):
        """Clear all data from the store."""
        with self._lock:
            self._create_empty()
            self._save()
    
    @property
    def document_count(self) -> int:
        """Number of documents in store."""
        return len(self.chunks)


class VectorStoreManager:
    """Manages vector stores for multiple clients."""
    
    _stores: Dict[str, ClientVectorStore] = {}
    _lock = threading.Lock()
    
    @classmethod
    def get_store(cls, client_id: str) -> ClientVectorStore:
        """Get or create vector store for client."""
        if client_id not in cls._stores:
            with cls._lock:
                if client_id not in cls._stores:
                    cls._stores[client_id] = ClientVectorStore(client_id)
        return cls._stores[client_id]
    
    @classmethod
    def clear_store(cls, client_id: str):
        """Clear and remove a client's store."""
        if client_id in cls._stores:
            with cls._lock:
                if client_id in cls._stores:
                    cls._stores[client_id].clear()
                    del cls._stores[client_id]
