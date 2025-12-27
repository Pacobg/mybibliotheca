#!/usr/bin/env python3
"""
Rebuild Search Index Script

Rebuilds the SQLite FTS5 search index from all books in KuzuDB.

Usage:
    python scripts/rebuild_search_index.py

Author: MyBibliotheca Performance Team
Created: 2025-12-27
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.search_index_service import SearchIndexService, get_search_index
from app.infrastructure.kuzu_graph import safe_execute_kuzu_query
from app.utils.safe_kuzu_manager import get_safe_kuzu_manager
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_all_books_from_kuzu() -> list:
    """
    Get all books from KuzuDB with authors
    
    Returns:
        List of book dictionaries
    """
    
    logger.info("📚 Loading books from KuzuDB...")
    
    # Query to get all books with their authors
    query = """
    MATCH (b:Book)
    OPTIONAL MATCH (b)-[:WRITTEN_BY|CONTRIBUTED_TO]->(a:Author)
    WITH b, COLLECT(DISTINCT a.name) AS author_names
    RETURN b, author_names
    ORDER BY b.title
    """
    
    try:
        result = safe_execute_kuzu_query(
            query=query,
            params={},
            user_id="rebuild_index",
            operation="rebuild_search_index"
        )
        
        books = []
        
        # Convert result to list
        if result:
            if hasattr(result, 'has_next') and hasattr(result, 'get_next'):
                while result.has_next():
                    row = result.get_next()
                    if len(row) >= 2:
                        book_data = dict(row[0]) if hasattr(row[0], '__dict__') else row[0]
                        authors = row[1] if isinstance(row[1], list) else []
                        
                        # Ensure book_data is a dict
                        if not isinstance(book_data, dict):
                            if hasattr(book_data, '__dict__'):
                                book_data = book_data.__dict__
                            else:
                                continue
                        
                        # Add authors to book data
                        book_data['authors'] = [a for a in authors if a]
                        
                        books.append(book_data)
            elif isinstance(result, list):
                for row in result:
                    if isinstance(row, dict):
                        book_data = row.get('col_0', {})
                        authors = row.get('col_1', [])
                        
                        if isinstance(book_data, dict):
                            book_data['authors'] = authors if isinstance(authors, list) else []
                            books.append(book_data)
        
        logger.info(f"✅ Found {len(books)} books")
        return books
        
    except Exception as e:
        logger.error(f"❌ Error loading books from KuzuDB: {e}")
        import traceback
        traceback.print_exc()
        return []


def rebuild_index():
    """Rebuild the search index"""
    
    print("="*60)
    print("REBUILDING SEARCH INDEX")
    print("="*60)
    print()
    
    # Get all books
    books = get_all_books_from_kuzu()
    
    if not books:
        print("❌ No books found in database!")
        return 1
    
    # Initialize search index
    search_index = get_search_index()
    
    # Rebuild index
    start_time = time.time()
    
    try:
        search_index.rebuild(books)
        
        duration = time.time() - start_time
        
        # Get stats
        stats = search_index.get_stats()
        
        print()
        print("="*60)
        print("REBUILD COMPLETE")
        print("="*60)
        print(f"📊 Statistics:")
        print(f"   Total books: {len(books)}")
        print(f"   Indexed: {stats['total_books']}")
        print(f"   Duration: {duration:.1f}s")
        print(f"   Speed: {len(books) / duration:.1f} books/sec")
        print()
        print(f"📊 Index Statistics:")
        print(f"   Total books: {stats['total_books']}")
        print(f"   DB size: {stats['db_size_mb']} MB")
        print(f"   Last rebuild: {stats['last_rebuild']}")
        print()
        print("="*60)
        print("✅ Search index is ready!")
        print("="*60)
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Error rebuilding index: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = rebuild_index()
    sys.exit(exit_code)
