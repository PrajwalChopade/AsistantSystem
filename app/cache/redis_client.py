"""
Redis client singleton with connection pooling.
"""

import redis
import json
from typing import Optional, Any
import threading

from app.config import settings


class RedisClient:
    """Thread-safe Redis client singleton."""
    
    _instance = None
    _lock = threading.Lock()
    _pool: Optional[redis.ConnectionPool] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize Redis connection pool."""
        try:
            self._pool = redis.ConnectionPool(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                max_connections=50,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            self._client = redis.Redis(connection_pool=self._pool)
            # Test connection
            self._client.ping()
            print(f"✅ Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            self._connected = True
        except redis.ConnectionError as e:
            print(f"⚠️ Redis connection failed: {e}. Caching disabled.")
            self._client = None
            self._connected = False
    
    @property
    def is_connected(self) -> bool:
        """Check if Redis is available."""
        if not self._client:
            return False
        try:
            self._client.ping()
            return True
        except:
            return False
    
    def get(self, key: str) -> Optional[str]:
        """Get value from Redis."""
        if not self._client:
            return None
        try:
            return self._client.get(key)
        except redis.RedisError as e:
            print(f"⚠️ Redis GET error: {e}")
            return None
    
    def set(
        self, 
        key: str, 
        value: str, 
        ttl: int = None
    ) -> bool:
        """Set value in Redis with optional TTL."""
        if not self._client:
            return False
        try:
            ttl = ttl or settings.CACHE_TTL_SECONDS
            self._client.setex(key, ttl, value)
            return True
        except redis.RedisError as e:
            print(f"⚠️ Redis SET error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        if not self._client:
            return False
        try:
            self._client.delete(key)
            return True
        except redis.RedisError as e:
            print(f"⚠️ Redis DELETE error: {e}")
            return False
    
    def get_json(self, key: str) -> Optional[Any]:
        """Get and deserialize JSON value."""
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None
    
    def set_json(self, key: str, value: Any, ttl: int = None) -> bool:
        """Serialize and set JSON value."""
        try:
            json_str = json.dumps(value)
            return self.set(key, json_str, ttl)
        except (TypeError, ValueError) as e:
            print(f"⚠️ JSON serialization error: {e}")
            return False
    
    def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field value."""
        if not self._client:
            return None
        try:
            return self._client.hget(name, key)
        except redis.RedisError:
            return None
    
    def hset(self, name: str, key: str, value: str) -> bool:
        """Set hash field value."""
        if not self._client:
            return False
        try:
            self._client.hset(name, key, value)
            return True
        except redis.RedisError:
            return False
    
    def hgetall(self, name: str) -> dict:
        """Get all hash fields."""
        if not self._client:
            return {}
        try:
            return self._client.hgetall(name) or {}
        except redis.RedisError:
            return {}
    
    def acquire_lock(self, name: str, timeout: int = 10) -> Optional[redis.lock.Lock]:
        """Acquire a distributed lock."""
        if not self._client:
            return None
        try:
            lock = self._client.lock(name, timeout=timeout, blocking_timeout=5)
            if lock.acquire(blocking=True):
                return lock
            return None
        except redis.RedisError:
            return None
    
    def incr(self, key: str) -> int:
        """Increment a counter."""
        if not self._client:
            return 0
        try:
            return self._client.incr(key)
        except redis.RedisError:
            return 0


# Module-level singleton accessor
def get_redis_client() -> RedisClient:
    """Get the singleton Redis client instance."""
    return RedisClient()
