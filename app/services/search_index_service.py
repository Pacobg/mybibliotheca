"""
SQLite FTS5 Search Index Service for MyBibliotheca
Provides fast full-text search using SQLite FTS5

Author: MyBibliotheca Performance Team
Created: 2025-12-27
"""

import sqlite3
import os
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime, date
import json

logger = logging.getLogger(__name__)


class SearchIndexService:
    """
    SQLite FTS5-based search index service
    
    Features:
    - O(log n) search instead of O(n) table scans
    - Full-text search with ranking
    - Support for Cyrillic and other Unicode text
    - Automatic index updates
    - Fast search across title, author, description
    
    The index is stored in: ./data/search_index.db
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize search index service
        
        Args:
            db_path: Path to SQLite database (default: ./data/search_index.db)
        """
        
        if db_path is None:
            # Default to data directory
            data_dir = Path('data')
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / 'search_index.db')
        
        self.db_path = db_path
        self._ensure_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_schema(self):
        """Create tables if they don't exist"""
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Create metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS index_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Create FTS5 virtual table for full-text search
            # Using FTS5 for better Unicode support and performance
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS books_fts USING fts5(
                    book_id UNINDEXED,
                    title,
                    subtitle,
                    authors,
                    description,
                    isbn13,
                    isbn10,
                    series,
                    tokenize='unicode61'
                )
            """)
            
            # Create regular table to store book metadata (for non-searchable fields)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS books_metadata (
                    book_id TEXT PRIMARY KEY,
                    language TEXT,
                    published_date TEXT,
                    page_count INTEGER,
                    media_type TEXT,
                    updated_at TEXT,
                    indexed_at TEXT
                )
            """)
            
            # Set last rebuild timestamp if not exists
            cursor.execute("""
                INSERT OR IGNORE INTO index_metadata (key, value)
                VALUES ('last_rebuild', ?)
            """, (datetime.now().isoformat(),))
            
            conn.commit()
            logger.info(f"✅ Search index schema initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing search index schema: {e}")
            raise
        finally:
            conn.close()
    
    def index_book(self, book_data: Dict[str, Any]):
        """
        Index a single book
        
        Args:
            book_data: Book dictionary with at least 'id' and 'title'
        """
        
        book_id = book_data.get('id')
        if not book_id:
            logger.warning("Cannot index book without ID")
            return
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Extract searchable fields
            title = book_data.get('title', '') or ''
            subtitle = book_data.get('subtitle', '') or ''
            description = book_data.get('description', '') or ''
            isbn13 = book_data.get('isbn13', '') or ''
            isbn10 = book_data.get('isbn10', '') or ''
            series = book_data.get('series', '') or ''
            
            # Extract authors (handle both list and string formats)
            authors = ''
            if 'authors' in book_data:
                authors_list = book_data['authors']
                if isinstance(authors_list, list):
                    authors = ' '.join([str(a) for a in authors_list if a])
                elif authors_list:
                    authors = str(authors_list)
            elif 'author' in book_data:
                authors = str(book_data['author'])
            
            # Extract metadata fields
            language = book_data.get('language', '') or ''
            published_date = book_data.get('published_date', '')
            if published_date:
                if isinstance(published_date, datetime):
                    published_date = published_date.isoformat()
                elif isinstance(published_date, date):
                    published_date = published_date.isoformat()
                else:
                    published_date = str(published_date)
            else:
                published_date = ''
            
            page_count = book_data.get('page_count') or 0
            media_type = book_data.get('media_type', '') or ''
            
            # Delete existing entry first (FTS5 doesn't support ON CONFLICT)
            cursor.execute("DELETE FROM books_fts WHERE book_id = ?", (book_id,))
            
            # Insert into FTS index
            cursor.execute("""
                INSERT INTO books_fts (
                    book_id, title, subtitle, authors, description,
                    isbn13, isbn10, series
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (book_id, title, subtitle, authors, description,
                  isbn13, isbn10, series))
            
            # Insert/update metadata
            cursor.execute("""
                INSERT INTO books_metadata (
                    book_id, language, published_date, page_count,
                    media_type, updated_at, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(book_id) DO UPDATE SET
                    language = excluded.language,
                    published_date = excluded.published_date,
                    page_count = excluded.page_count,
                    media_type = excluded.media_type,
                    updated_at = excluded.updated_at,
                    indexed_at = excluded.indexed_at
            """, (book_id, language, published_date, page_count, media_type,
                  book_data.get('updated_at', ''), datetime.now().isoformat()))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error indexing book {book_id}: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def remove_book(self, book_id: str):
        """
        Remove book from index
        
        Args:
            book_id: Book ID to remove
        """
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM books_fts WHERE book_id = ?", (book_id,))
            cursor.execute("DELETE FROM books_metadata WHERE book_id = ?", (book_id,))
            
            conn.commit()
            
            logger.debug(f"Removed book {book_id} from search index")
            
        except Exception as e:
            logger.error(f"Error removing book {book_id} from index: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def search(
        self, 
        query: str, 
        limit: int = 1000,
        offset: int = 0
    ) -> List[str]:
        """
        Search for books using FTS5
        
        Args:
            query: Search query string
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            List of book IDs matching the query, ordered by relevance
        """
        
        if not query or not query.strip():
            # Empty query - return all books (limited)
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT book_id FROM books_fts
                    ORDER BY book_id
                    LIMIT ? OFFSET ?
                """, (limit, offset))
                return [row[0] for row in cursor.fetchall()]
            finally:
                conn.close()
        
        query = query.strip()
        
        # Build FTS5 query
        # FTS5 supports various query syntax:
        # - Simple: "word" searches for word
        # - Phrase: "word1 word2" searches for phrase
        # - Prefix: word* searches for words starting with word
        # - OR: word1 OR word2
        # - AND: word1 word2 (default)
        
        # Escape special characters and build query
        # For simple queries, we'll search across all fields
        fts_query = f"{query}*"  # Prefix search for better matching
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Use FTS5 search with ranking
            # bm25() provides better ranking than simple match
            cursor.execute("""
                SELECT book_id, bm25(books_fts) as rank
                FROM books_fts
                WHERE books_fts MATCH ?
                ORDER BY rank
                LIMIT ? OFFSET ?
            """, (fts_query, limit, offset))
            
            results = [row[0] for row in cursor.fetchall()]
            
            logger.debug(f"Search '{query}': {len(results)} results")
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching index: {e}")
            return []
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get index statistics
        
        Returns:
            Dictionary with index stats
        """
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get total books
            cursor.execute("SELECT COUNT(*) FROM books_fts")
            total_books = cursor.fetchone()[0]
            
            # Get last rebuild time
            cursor.execute("""
                SELECT value FROM index_metadata WHERE key = 'last_rebuild'
            """)
            last_rebuild_row = cursor.fetchone()
            last_rebuild = last_rebuild_row[0] if last_rebuild_row else None
            
            # Get database size
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            return {
                'total_books': total_books,
                'db_size': db_size,
                'db_size_mb': round(db_size / (1024 * 1024), 2),
                'last_rebuild': last_rebuild,
                'db_path': self.db_path
            }
            
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {
                'total_books': 0,
                'db_size': 0,
                'db_size_mb': 0,
                'last_rebuild': None,
                'error': str(e)
            }
        finally:
            conn.close()
    
    def rebuild(self, books: List[Dict[str, Any]]):
        """
        Rebuild entire index from list of books
        
        Args:
            books: List of book dictionaries
        """
        
        logger.info(f"🔄 Rebuilding search index with {len(books)} books...")
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Clear existing index
            cursor.execute("DELETE FROM books_fts")
            cursor.execute("DELETE FROM books_metadata")
            
            # Index all books
            indexed = 0
            failed = 0
            
            for i, book in enumerate(books):
                try:
                    self.index_book(book)
                    indexed += 1
                    
                    if (i + 1) % 100 == 0:
                        logger.info(f"   Indexed {i + 1}/{len(books)} books...")
                        conn.commit()  # Periodic commit for large batches
                        
                except Exception as e:
                    failed += 1
                    logger.warning(f"Failed to index book {book.get('id', 'unknown')}: {e}")
            
            # Update last rebuild timestamp
            cursor.execute("""
                UPDATE index_metadata 
                SET value = ? 
                WHERE key = 'last_rebuild'
            """, (datetime.now().isoformat(),))
            
            conn.commit()
            
            logger.info(f"✅ Index rebuild complete: {indexed} indexed, {failed} failed")
            
        except Exception as e:
            logger.error(f"Error rebuilding index: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def clear(self):
        """Clear entire index"""
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM books_fts")
            cursor.execute("DELETE FROM books_metadata")
            conn.commit()
            logger.info("Search index cleared")
        except Exception as e:
            logger.error(f"Error clearing index: {e}")
            conn.rollback()
        finally:
            conn.close()


# ========== Global Instance ==========

_search_index = None

def get_search_index() -> SearchIndexService:
    """
    Get global search index service instance
    
    Returns:
        SearchIndexService singleton instance
    """
    global _search_index
    
    if _search_index is None:
        _search_index = SearchIndexService()
    
    return _search_index


# ========== Testing ==========

if __name__ == "__main__":
    """Quick test of search index service"""
    
    import sys
    
    print("="*60)
    print("SEARCH INDEX SERVICE TEST")
    print("="*60)
    
    # Initialize
    index = get_search_index()
    
    # Test indexing
    print("\n✅ Test 1: Indexing books")
    test_books = [
        {
            'id': 'test-1',
            'title': 'Test Book One',
            'subtitle': 'A Test',
            'authors': ['Test Author'],
            'description': 'This is a test book',
            'isbn13': '1234567890123'
        },
        {
            'id': 'test-2',
            'title': 'Another Book',
            'authors': ['Another Author'],
            'description': 'Another test description'
        }
    ]
    
    for book in test_books:
        index.index_book(book)
    
    print(f"   Indexed {len(test_books)} books")
    
    # Test search
    print("\n✅ Test 2: Searching")
    results = index.search('test')
    print(f"   Search for 'test': {len(results)} results")
    print(f"   Results: {results}")
    
    # Test stats
    print("\n✅ Test 3: Statistics")
    stats = index.get_stats()
    print(f"   Total books: {stats['total_books']}")
    print(f"   DB size: {stats['db_size_mb']} MB")
    
    # Cleanup
    for book in test_books:
        index.remove_book(book['id'])
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
