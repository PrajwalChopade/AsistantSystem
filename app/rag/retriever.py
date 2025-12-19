"""
Document retriever with confidence scoring.
Enforces document-grounded responses.
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass

from app.config import settings
from app.rag.vectorstore import VectorStoreManager, RetrievalResult


@dataclass
class RetrievalResponse:
    """Response from document retrieval."""
    context: str
    confidence: float
    sources: List[str]
    is_relevant: bool
    chunks: List[RetrievalResult]


class DocumentRetriever:
    """Retrieves relevant document context for queries."""
    
    NO_DOCS_MESSAGE = "This information is not available in the provided documentation."
    
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.store = VectorStoreManager.get_store(client_id)
    
    def retrieve(
        self, 
        query: str,
        top_k: int = None,
        min_score: float = None
    ) -> RetrievalResponse:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: User's question
            top_k: Number of chunks to retrieve
            min_score: Minimum similarity threshold
            
        Returns:
            RetrievalResponse with context and confidence
        """
        top_k = top_k or settings.RETRIEVAL_TOP_K
        min_score = min_score if min_score is not None else settings.SIMILARITY_THRESHOLD
        
        # Check if store has documents
        if self.store.document_count == 0:
            return RetrievalResponse(
                context="",
                confidence=0.0,
                sources=[],
                is_relevant=False,
                chunks=[]
            )
        
        # Search vector store
        results = self.store.search(query, top_k=top_k, min_score=min_score)
        
        if not results:
            return RetrievalResponse(
                context="",
                confidence=0.0,
                sources=[],
                is_relevant=False,
                chunks=[]
            )
        
        # Calculate overall confidence (weighted average of scores)
        total_score = sum(r.score for r in results)
        avg_confidence = total_score / len(results)
        
        # Combine context from results
        context_parts = []
        sources = set()
        
        for result in results:
            context_parts.append(result.content)
            if "source" in result.metadata:
                sources.add(result.metadata["source"])
        
        combined_context = "\n\n---\n\n".join(context_parts)
        
        # Determine if results are relevant enough
        is_relevant = (
            avg_confidence >= min_score and 
            results[0].score >= min_score
        )
        
        return RetrievalResponse(
            context=combined_context,
            confidence=avg_confidence,
            sources=list(sources),
            is_relevant=is_relevant,
            chunks=results
        )
    
    def get_store_version(self) -> str:
        """Get current document store version for cache keying."""
        return self.store.version
    
    @property
    def has_documents(self) -> bool:
        """Check if client has any documents indexed."""
        return self.store.document_count > 0


def retrieve_for_client(client_id: str, query: str) -> RetrievalResponse:
    """Convenience function to retrieve documents for a client."""
    retriever = DocumentRetriever(client_id)
    return retriever.retrieve(query)
