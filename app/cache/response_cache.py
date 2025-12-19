"""
Response caching with document version awareness.
"""

import hashlib
import json
import re
from typing import Optional, Dict, Any
from datetime import datetime

from app.cache.redis_client import get_redis_client
from app.config import settings


class ResponseCache:
    """Caches query responses with document versioning."""
    
    CACHE_PREFIX = "response:"
    METRICS_KEY = "cache:metrics"
    
    def __init__(self):
        self.redis = get_redis_client()
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent cache keys."""
        # Lowercase
        normalized = query.lower().strip()
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        # Remove punctuation except essential ones
        normalized = re.sub(r'[^\w\s\?\.]', '', normalized)
        return normalized
    
    def _generate_cache_key(
        self, 
        client_id: str, 
        query: str, 
        doc_version: str
    ) -> str:
        """Generate cache key from client_id + normalized_query + doc_version."""
        normalized = self._normalize_query(query)
        key_content = f"{client_id}:{normalized}:{doc_version}"
        key_hash = hashlib.sha256(key_content.encode()).hexdigest()[:32]
        return f"{self.CACHE_PREFIX}{key_hash}"
    
    def get(
        self, 
        client_id: str, 
        query: str, 
        doc_version: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response if exists.
        
        Args:
            client_id: Client identifier
            query: User query
            doc_version: Current document version hash
            
        Returns:
            Cached response dict or None
        """
        cache_key = self._generate_cache_key(client_id, query, doc_version)
        cached = self.redis.get_json(cache_key)
        
        if cached:
            self._record_hit()
            return cached
        
        self._record_miss()
        return None
    
    def set(
        self, 
        client_id: str, 
        query: str, 
        doc_version: str,
        response: Dict[str, Any],
        ttl: int = None
    ) -> bool:
        """
        Cache a response.
        
        Args:
            client_id: Client identifier
            query: User query  
            doc_version: Current document version hash
            response: Response to cache
            ttl: Optional TTL override
            
        Returns:
            True if cached successfully
        """
        cache_key = self._generate_cache_key(client_id, query, doc_version)
        
        # Add cache metadata
        cached_response = {
            **response,
            "_cached_at": datetime.utcnow().isoformat(),
            "_doc_version": doc_version
        }
        
        return self.redis.set_json(cache_key, cached_response, ttl)
    
    def invalidate(self, client_id: str, query: str, doc_version: str) -> bool:
        """Invalidate a specific cached response."""
        cache_key = self._generate_cache_key(client_id, query, doc_version)
        return self.redis.delete(cache_key)
    
    def _record_hit(self):
        """Record cache hit metric."""
        self.redis.incr(f"{self.METRICS_KEY}:hits")
    
    def _record_miss(self):
        """Record cache miss metric."""
        self.redis.incr(f"{self.METRICS_KEY}:misses")
    
    def get_metrics(self) -> Dict[str, int]:
        """Get cache hit/miss metrics."""
        hits = int(self.redis.get(f"{self.METRICS_KEY}:hits") or 0)
        misses = int(self.redis.get(f"{self.METRICS_KEY}:misses") or 0)
        total = hits + misses
        
        return {
            "hits": hits,
            "misses": misses,
            "total": total,
            "hit_rate": round(hits / total, 3) if total > 0 else 0.0
        }


class ConversationCache:
    """Manages conversation state in Redis."""
    
    CONV_PREFIX = "conversation:"
    
    def __init__(self):
        self.redis = get_redis_client()
    
    def _get_key(self, client_id: str, user_id: str) -> str:
        """Generate conversation key."""
        return f"{self.CONV_PREFIX}{client_id}:{user_id}"
    
    def get_history(
        self, 
        client_id: str, 
        user_id: str, 
        max_turns: int = 10
    ) -> list:
        """Get conversation history."""
        key = self._get_key(client_id, user_id)
        history = self.redis.get_json(key)
        
        if history and isinstance(history, list):
            return history[-max_turns:]
        return []
    
    def add_turn(
        self, 
        client_id: str, 
        user_id: str, 
        user_message: str, 
        assistant_reply: str
    ):
        """Add a conversation turn."""
        key = self._get_key(client_id, user_id)
        history = self.get_history(client_id, user_id, max_turns=20)
        
        history.append({
            "user": user_message,
            "assistant": assistant_reply,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep only last 20 turns
        history = history[-20:]
        
        # Cache for 24 hours
        self.redis.set_json(key, history, ttl=86400)
    
    def clear(self, client_id: str, user_id: str):
        """Clear conversation history."""
        key = self._get_key(client_id, user_id)
        self.redis.delete(key)


# Singleton instances
_response_cache: Optional[ResponseCache] = None
_conversation_cache: Optional[ConversationCache] = None


def get_response_cache() -> ResponseCache:
    """Get singleton response cache."""
    global _response_cache
    if _response_cache is None:
        _response_cache = ResponseCache()
    return _response_cache


def get_conversation_cache() -> ConversationCache:
    """Get singleton conversation cache."""
    global _conversation_cache
    if _conversation_cache is None:
        _conversation_cache = ConversationCache()
    return _conversation_cache
