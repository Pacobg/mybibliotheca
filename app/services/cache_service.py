"""
Redis Cache Service for MyBibliotheca
Provides caching for search results, book data, and rendered content

Author: MyBibliotheca Performance Team
Created: 2025-12-27
"""

import redis
import json
import os
import logging
from typing import Optional, List, Dict, Any
from functools import wraps
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis-based caching service
    
    Features:
    - Search result caching (10-100x faster repeated searches)
    - Book data caching (instant retrieval)
    - Automatic cache invalidation
    - Graceful degradation (works even if Redis is down)
    
    Configuration via environment variables:
    - REDIS_HOST: Redis server hostname/IP
    - REDIS_PORT: Redis port (default: 6379)
    - REDIS_DB: Redis database number (default: 0)
    - REDIS_PASSWORD: Redis password (optional)
    - REDIS_ENABLED: Enable/disable caching (default: true)
    """
    
    def __init__(self):
        """Initialize Redis connection"""
        
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        self.redis_password = os.getenv('REDIS_PASSWORD')
        self.enabled = os.getenv('REDIS_ENABLED', 'true').lower() == 'true'
        
        if not self.enabled:
            logger.info("⚠️  Redis caching is disabled via REDIS_ENABLED=false")
            return
        
        try:
            self.redis = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.redis.ping()
            
            logger.info(f"✅ Redis cache connected: {self.redis_host}:{self.redis_port}")
            
        except (redis.ConnectionError, redis.TimeoutError) as e:
            self.enabled = False
            logger.warning(f"⚠️  Redis not available, caching disabled: {e}")
        except Exception as e:
            self.enabled = False
            logger.error(f"❌ Redis initialization error: {e}")
    
    # ========== Search Result Caching ==========
    
    def get_search_results(
        self, 
        query: str, 
        filters: Optional[Dict] = None
    ) -> Optional[List[str]]:
        """
        Get cached search results
        
        Args:
            query: Search query string
            filters: Optional filters (page, language, etc)
            
        Returns:
            List of book IDs or None if cache miss
        """
        
        if not self.enabled:
            return None
        
        try:
            cache_key = self._make_search_key(query, filters)
            cached = self.redis.get(cache_key)
            
            if cached:
                logger.debug(f"🎯 Cache HIT: search '{query[:30]}...'")
                return json.loads(cached)
            
            logger.debug(f"❌ Cache MISS: search '{query[:30]}...'")
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def cache_search_results(
        self, 
        query: str, 
        book_ids: List[str],
        filters: Optional[Dict] = None,
        ttl: int = 3600
    ):
        """
        Cache search results
        
        Args:
            query: Search query string
            book_ids: List of book IDs
            filters: Optional filters
            ttl: Time to live in seconds (default: 1 hour)
        """
        
        if not self.enabled:
            return
        
        try:
            cache_key = self._make_search_key(query, filters)
            self.redis.setex(
                cache_key,
                ttl,
                json.dumps(book_ids)
            )
            
            logger.debug(f"💾 Cached search: '{query[:30]}...' ({len(book_ids)} results)")
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    def _make_search_key(self, query: str, filters: Optional[Dict] = None) -> str:
        """
        Generate cache key for search
        
        Args:
            query: Search query
            filters: Optional filters
            
        Returns:
            Cache key string
        """
        
        key_parts = ['search', query.lower().strip()]
        
        if filters:
            # Create deterministic hash of filters
            filter_str = json.dumps(filters, sort_keys=True)
            filter_hash = hashlib.md5(filter_str.encode()).hexdigest()[:8]
            key_parts.append(filter_hash)
        
        return ':'.join(key_parts)
    
    # ========== Book Data Caching ==========
    
    def get_book(self, book_id: str) -> Optional[Dict]:
        """
        Get cached book data
        
        Args:
            book_id: Book ID
            
        Returns:
            Book dictionary or None if cache miss
        """
        
        if not self.enabled:
            return None
        
        try:
            cache_key = f"book:{book_id}"
            cached = self.redis.get(cache_key)
            
            if cached:
                logger.debug(f"🎯 Cache HIT: book {book_id}")
                return json.loads(cached)
            
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def cache_book(
        self, 
        book_id: str, 
        book_data: Dict, 
        ttl: int = 3600
    ):
        """
        Cache book data
        
        Args:
            book_id: Book ID
            book_data: Book data dictionary
            ttl: Time to live in seconds (default: 1 hour)
        """
        
        if not self.enabled:
            return
        
        try:
            cache_key = f"book:{book_id}"
            
            # Serialize book data
            serializable_data = self._make_serializable(book_data)
            
            self.redis.setex(
                cache_key,
                ttl,
                json.dumps(serializable_data, default=str)
            )
            
            logger.debug(f"💾 Cached book: {book_id}")
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    def cache_multiple_books(
        self, 
        books: List[Dict], 
        ttl: int = 3600
    ):
        """
        Cache multiple books at once (pipeline for efficiency)
        
        Args:
            books: List of book dictionaries (must have 'id' field)
            ttl: Time to live in seconds
        """
        
        if not self.enabled or not books:
            return
        
        try:
            pipe = self.redis.pipeline()
            
            for book in books:
                book_id = book.get('id')
                if not book_id:
                    continue
                
                cache_key = f"book:{book_id}"
                serializable_data = self._make_serializable(book)
                
                pipe.setex(
                    cache_key, 
                    ttl, 
                    json.dumps(serializable_data, default=str)
                )
            
            pipe.execute()
            
            logger.debug(f"💾 Cached {len(books)} books")
            
        except Exception as e:
            logger.error(f"Cache pipeline error: {e}")
    
    # ========== Cache Invalidation ==========
    
    def invalidate_book(self, book_id: str):
        """
        Invalidate book cache when updated
        
        Args:
            book_id: Book ID to invalidate
        """
        
        if not self.enabled:
            return
        
        try:
            cache_key = f"book:{book_id}"
            self.redis.delete(cache_key)
            
            logger.debug(f"🗑️  Invalidated book cache: {book_id}")
            
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
    
    def invalidate_all_searches(self):
        """
        Invalidate all search caches
        
        Call this when:
        - Books are added/removed
        - Search index is rebuilt
        - Bulk updates occur
        """
        
        if not self.enabled:
            return
        
        try:
            # Find all search keys
            count = 0
            for key in self.redis.scan_iter("search:*", count=100):
                self.redis.delete(key)
                count += 1
            
            if count > 0:
                logger.info(f"🗑️  Invalidated {count} search caches")
            
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
    
    def clear_all(self):
        """
        Clear all caches (use with caution!)
        
        This will flush the entire Redis database.
        Only use for testing or maintenance.
        """
        
        if not self.enabled:
            return
        
        try:
            self.redis.flushdb()
            logger.warning("🗑️  ALL CACHES CLEARED!")
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
    
    # ========== Statistics & Monitoring ==========
    
    def get_stats(self) -> Dict:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache stats
        """
        
        if not self.enabled:
            return {
                'enabled': False,
                'reason': 'Caching disabled or Redis unavailable'
            }
        
        try:
            info = self.redis.info()
            
            # Calculate hit rate
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            total = hits + misses
            hit_rate = (hits / total * 100) if total > 0 else 0
            
            stats = {
                'enabled': True,
                'connected': True,
                'host': f"{self.redis_host}:{self.redis_port}",
                'db': self.redis_db,
                'total_keys': self.redis.dbsize(),
                'memory_used': info.get('used_memory_human', 'N/A'),
                'memory_peak': info.get('used_memory_peak_human', 'N/A'),
                'hits': hits,
                'misses': misses,
                'hit_rate': round(hit_rate, 2),
                'uptime_seconds': info.get('uptime_in_seconds', 0),
                'connected_clients': info.get('connected_clients', 0),
                'version': info.get('redis_version', 'unknown')
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                'enabled': False,
                'error': str(e)
            }
    
    def health_check(self) -> bool:
        """
        Check if Redis is healthy
        
        Returns:
            True if Redis is accessible and responding
        """
        
        if not self.enabled:
            return False
        
        try:
            return self.redis.ping()
        except:
            return False
    
    # ========== Utilities ==========
    
    @staticmethod
    def _make_serializable(data: Any) -> Any:
        """
        Make data JSON serializable
        
        Handles:
        - Objects with __dict__
        - datetime objects
        - Sets, tuples
        - Nested structures
        
        Args:
            data: Data to serialize
            
        Returns:
            JSON-serializable version of data
        """
        
        if isinstance(data, dict):
            return {
                k: CacheService._make_serializable(v)
                for k, v in data.items()
                if not k.startswith('_')  # Skip internal fields
            }
        elif isinstance(data, (list, tuple)):
            return [CacheService._make_serializable(item) for item in data]
        elif isinstance(data, set):
            return list(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        elif hasattr(data, '__dict__'):
            # Convert object to dict
            return CacheService._make_serializable(data.__dict__)
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            # Convert to string as fallback
            return str(data)
    
    def close(self):
        """Close Redis connection"""
        if self.enabled and hasattr(self, 'redis'):
            try:
                self.redis.close()
                logger.info("Redis connection closed")
            except:
                pass


# ========== Decorator for Caching Function Results ==========

def cached(ttl: int = 3600, key_prefix: str = ''):
    """
    Decorator for caching function results
    
    Usage:
        @cached(ttl=600, key_prefix='expensive_func')
        def expensive_function(arg1, arg2):
            # Do expensive computation
            return result
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key (default: function name)
    
    Returns:
        Decorated function
    """
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache_service()
            
            if not cache.enabled:
                # Cache disabled, execute function directly
                return func(*args, **kwargs)
            
            # Generate cache key from function name and arguments
            key_parts = [key_prefix or func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = ':'.join(key_parts)
            
            # Try to get from cache
            try:
                cached_result = cache.redis.get(cache_key)
                if cached_result:
                    logger.debug(f"🎯 Cache HIT: {func.__name__}")
                    return json.loads(cached_result)
            except Exception as e:
                logger.debug(f"Cache read error: {e}")
            
            # Cache miss - compute result
            logger.debug(f"❌ Cache MISS: {func.__name__}")
            result = func(*args, **kwargs)
            
            # Store in cache
            try:
                serializable = CacheService._make_serializable(result)
                cache.redis.setex(
                    cache_key,
                    ttl,
                    json.dumps(serializable, default=str)
                )
            except Exception as e:
                logger.debug(f"Cache write error: {e}")
            
            return result
        
        return wrapper
    return decorator


# ========== Global Instance ==========

_cache_service = None

def get_cache_service() -> CacheService:
    """
    Get global cache service instance
    
    Returns:
        CacheService singleton instance
    """
    global _cache_service
    
    if _cache_service is None:
        _cache_service = CacheService()
    
    return _cache_service


# ========== Testing ==========

if __name__ == "__main__":
    """Quick test of cache service"""
    
    import sys
    
    print("="*60)
    print("CACHE SERVICE TEST")
    print("="*60)
    
    # Initialize
    cache = get_cache_service()
    
    if not cache.enabled:
        print("❌ Cache is disabled!")
        sys.exit(1)
    
    # Test basic operations
    print("\n✅ Test 1: Book caching")
    test_book = {
        'id': 'test-123',
        'title': 'Test Book',
        'author': 'Test Author'
    }
    
    cache.cache_book('test-123', test_book)
    retrieved = cache.get_book('test-123')
    print(f"   Stored and retrieved: {retrieved['title']}")
    
    # Test search caching
    print("\n✅ Test 2: Search caching")
    cache.cache_search_results('test query', ['book1', 'book2', 'book3'])
    results = cache.get_search_results('test query')
    print(f"   Search results: {len(results)} books")
    
    # Test stats
    print("\n✅ Test 3: Statistics")
    stats = cache.get_stats()
    print(f"   Total keys: {stats['total_keys']}")
    print(f"   Hit rate: {stats['hit_rate']}%")
    print(f"   Memory: {stats['memory_used']}")
    
    # Cleanup
    cache.invalidate_book('test-123')
    cache.invalidate_all_searches()
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
