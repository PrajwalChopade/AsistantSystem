"""
Local embedding model singleton.
Loaded once at startup and reused across all requests.
"""

import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Union
import threading

from app.config import settings


class EmbeddingModel:
    """Thread-safe singleton for local embedding model."""
    
    _instance = None
    _lock = threading.Lock()
    _model: SentenceTransformer = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Load the embedding model once."""
        print(f"📦 Loading embedding model: {settings.EMBEDDING_MODEL_NAME}")
        self._model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        print("✅ Embedding model loaded successfully")
    
    def embed(self, text: Union[str, List[str]], normalize: bool = True) -> np.ndarray:
        """
        Generate embeddings for text(s).
        
        Args:
            text: Single string or list of strings to embed
            normalize: Whether to L2-normalize embeddings (default True for cosine similarity)
            
        Returns:
            numpy array of shape (n, embedding_dim) for list input, or (embedding_dim,) for single string
        """
        if isinstance(text, str):
            return self._model.encode(
                text, 
                normalize_embeddings=normalize,
                show_progress_bar=False
            ).astype("float32")
        else:
            return self._model.encode(
                text, 
                normalize_embeddings=normalize,
                show_progress_bar=False,
                batch_size=32
            ).astype("float32")
    
    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string."""
        return self.embed(query, normalize=True)
    
    def embed_documents(self, documents: List[str]) -> np.ndarray:
        """Embed multiple documents."""
        return self.embed(documents, normalize=True)
    
    @property
    def dimension(self) -> int:
        """Return embedding dimension."""
        return settings.EMBEDDING_DIMENSION


# Module-level singleton accessor
def get_embedding_model() -> EmbeddingModel:
    """Get the singleton embedding model instance."""
    return EmbeddingModel()
