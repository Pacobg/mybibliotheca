#!/usr/bin/env python3
"""
MyBibliotheca Dev Script: Cleanup Invalid Categories
====================================================

This script cleans up invalid and duplicate categories from all books in the database.

It:
- Removes custom tags like "Books-i-own", "to-read", etc.
- Removes duplicate categories (case-insensitive)
- Removes author names from categories
- Updates books with cleaned categories
- Only works in development mode (FLASK_ENV=development or DEBUG=True)
"""

import os
import sys
import argparse
import asyncio
import logging
import re

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app import create_app
    from app.infrastructure.kuzu_graph import safe_execute_kuzu_query
    from app.services.kuzu_async_helper import run_async
    from config import Config
except ImportError as e:
    print(f"❌ Error importing application modules: {e}")
    print("🔧 Make sure you're running this from the MyBibliotheca directory")
    sys.exit(1)


def _convert_query_result_to_list(result):
    """Convert KuzuDB QueryResult to list format"""
    if result is None:
        return []
    
    rows = []
    try:
        if hasattr(result, 'has_next') and hasattr(result, 'get_next'):
            while result.has_next():
                row = result.get_next()
                if isinstance(row, (list, tuple)):
                    if len(row) == 1:
                        rows.append({'col_0': row[0], 'result': row[0]})
                    else:
                        row_dict = {}
                        for i, value in enumerate(row):
                            row_dict[f'col_{i}'] = value
                        rows.append(row_dict)
                elif isinstance(row, dict):
                    rows.append(row)
        elif isinstance(result, list):
            return result
    except Exception as e:
        logger.warning(f"Warning: Error converting result: {e}")
    
    return rows

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_dev_mode():
    """Check if we're in development mode"""
    flask_env = os.getenv('FLASK_ENV', '').lower()
    flask_debug = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'on', 'yes')
    mybibliotheca_debug = os.getenv('MYBIBLIOTHECA_DEBUG', '').lower() in ('1', 'true', 'on', 'yes')
    
    # First check environment variables
    if flask_env == 'development' or flask_debug or mybibliotheca_debug:
        return True
    
    # Then check config if available
    try:
        app = create_app()
        with app.app_context():
            is_dev = (
                (hasattr(Config, 'DEBUG') and Config.DEBUG) or
                (hasattr(Config, 'DEBUG_MODE') and Config.DEBUG_MODE) or
                (hasattr(Config, 'FLASK_ENV') and Config.FLASK_ENV == 'development')
            )
            return is_dev
    except Exception as e:
        logger.debug(f"Could not check config: {e}")
        return False


def _filter_invalid_categories(categories, author_name=None):
    """
    Filter out invalid categories like author names, generic terms, custom tags, etc.
    Also removes duplicates (case-insensitive).
    
    This is the same function as in app/routes/import_routes.py
    """
    if not categories:
        return []
    
    # Normalize author name for comparison
    author_parts = []
    if author_name:
        author_parts = [part.strip().lower() for part in author_name.replace(',', ' ').split() if part.strip()]
    
    exclude_terms = {
        # Generic terms
        'fiction', 'non-fiction', 'nonfiction', 'literature', 'general',
        'juvenile', 'adult', 'young adult', 'large print',
        # Custom tags (not real genres)
        'books-i-own', 'i-own', 'own', 'to-read', 'to read', 'read', 'reading',
        'want-to-read', 'want to read', 'currently-reading', 'currently reading',
        'favorites', 'favourites', 'favorite', 'favourite',
        'library', 'my-library', 'my library', 'personal-library', 'personal library',
        'collection', 'my-collection', 'my collection',
        'wishlist', 'wish-list', 'wish list',
        'ebook', 'e-book', 'e book', 'audiobook', 'audio-book', 'audio book',
        'physical', 'hardcover', 'hard-cover', 'hard cover', 'paperback', 'paper-back', 'paper back',
    }
    
    exclude_patterns = [
        r'^books?-i-own$',
        r'^i-own$',
        r'^own$',
        r'^to-?read$',
        r'^want-?to-?read$',
        r'^currently-?reading$',
        r'^my-?library$',
        r'^personal-?library$',
        r'^my-?collection$',
        r'^wish-?list$',
        r'^[0-9]+$',
        r'^[^a-zA-Zа-яА-Я0-9]+$',
    ]
    
    valid_categories = []
    seen_lower = set()
    
    for cat in categories:
        if not cat or not isinstance(cat, str):
            continue
        
        cat_original = cat.strip()
        cat_lower = cat_original.lower()
        
        if len(cat_lower) < 3:
            continue
        
        if cat_lower in seen_lower:
            continue
        
        if cat_lower in exclude_terms:
            continue
        
        if any(re.match(pattern, cat_lower) for pattern in exclude_patterns):
            continue
        
        if any(tag in cat_lower for tag in ['-i-', '-my-', '-own', '-read', '-library', '-collection']):
            if not any(legit in cat_lower for legit in ['science', 'studies', 'fiction', 'literature', 'history']):
                continue
        
        if author_parts:
            cat_words = cat_lower.replace('-', ' ').replace('_', ' ').split()
            if any(part in cat_words for part in author_parts if len(part) > 2):
                continue
            author_normalized = '-'.join(author_parts)
            if author_normalized in cat_lower or cat_lower in author_normalized:
                continue
        
        if re.match(r'^[a-z]+-[a-z]+$', cat_lower):
            continue
        
        valid_categories.append(cat_original)
        seen_lower.add(cat_lower)
    
    return valid_categories


def get_book_count():
    """Get total number of books in the database"""
    try:
        query = "MATCH (b:Book) RETURN COUNT(b) as count"
        result = safe_execute_kuzu_query(query, {})
        rows = _convert_query_result_to_list(result)
        if rows:
            first = rows[0]
            val = first.get('count') or first.get('col_0') or first.get('result')
            return int(val) if isinstance(val, (int, float, str)) else 0
        return 0
    except Exception as e:
        logger.error(f"❌ Error getting book count: {e}")
        return -1


def get_all_books_with_categories():
    """Get all books with their categories and authors"""
    try:
        query = """
        MATCH (b:Book)
        OPTIONAL MATCH (b)-[:CATEGORIZED_AS]->(c:Category)
        OPTIONAL MATCH (p:Person)-[r:AUTHORED {role: 'author', order_index: 0}]->(b)
        WITH b, COLLECT(DISTINCT c.name) as categories, COLLECT(DISTINCT p.name)[0] as author
        RETURN b.id as book_id, b.title as title, categories, author
        """
        result = safe_execute_kuzu_query(query, {})
        rows = _convert_query_result_to_list(result)
        
        books = []
        for row in rows:
            book_id = row.get('book_id') or row.get('col_0')
            title = row.get('title') or row.get('col_1') or 'Unknown'
            categories = row.get('categories') or row.get('col_2') or []
            author = row.get('author') or row.get('col_3')
            
            if book_id:
                books.append({
                    'id': book_id,
                    'title': title,
                    'categories': categories if isinstance(categories, list) else [],
                    'author': author
                })
        
        return books
    except Exception as e:
        logger.error(f"❌ Error getting books: {e}")
        import traceback
        traceback.print_exc()
        return []


async def cleanup_book_categories_async(book_id, filtered_categories):
    """Update categories for a single book"""
    try:
        # Remove all existing category relationships
        delete_query = """
        MATCH (b:Book {id: $book_id})-[r:CATEGORIZED_AS]->(c:Category)
        DELETE r
        """
        safe_execute_kuzu_query(delete_query, {"book_id": book_id})
        
        # Add new category relationships
        from app.infrastructure.kuzu_repositories import KuzuBookRepository
        book_repo = KuzuBookRepository()
        
        if filtered_categories:
            await book_repo._create_category_relationships_from_raw(book_id, filtered_categories)
        
        return True
    except Exception as e:
        logger.error(f"❌ Error updating categories for book {book_id}: {e}")
        return False


async def cleanup_all_categories_async(dry_run=False):
    """Cleanup categories for all books"""
    try:
        logger.info("📚 Fetching all books with categories...")
        books = get_all_books_with_categories()
        
        if not books:
            logger.info("✅ No books found in the database.")
            return True
        
        logger.info(f"📊 Found {len(books)} books to process.")
    except Exception as e:
        logger.error(f"❌ Error fetching books: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    total_removed = 0
    total_kept = 0
    books_updated = 0
    books_unchanged = 0
    
    for i, book in enumerate(books, 1):
        book_id = book['id']
        title = book['title']
        original_categories = book['categories']
        author = book.get('author')
        
        if not original_categories:
            continue
        
        # Filter categories
        filtered_categories = _filter_invalid_categories(original_categories, author_name=author)
        
        removed_count = len(original_categories) - len(filtered_categories)
        if removed_count > 0:
            total_removed += removed_count
            total_kept += len(filtered_categories)
            
            if not dry_run:
                success = await cleanup_book_categories_async(book_id, filtered_categories)
                if success:
                    books_updated += 1
                    logger.info(f"✅ [{i}/{len(books)}] Updated '{title}': removed {removed_count} invalid categories, kept {len(filtered_categories)}")
                else:
                    logger.warning(f"⚠️ [{i}/{len(books)}] Failed to update '{title}'")
            else:
                books_updated += 1
                logger.info(f"🔍 [{i}/{len(books)}] Would update '{title}': remove {removed_count} invalid categories, keep {len(filtered_categories)}")
                logger.debug(f"   Original: {original_categories}")
                logger.debug(f"   Filtered: {filtered_categories}")
        else:
            books_unchanged += 1
        
        if i % 50 == 0:
            logger.info(f"📊 Progress: {i}/{len(books)} books processed...")
    
    logger.info("=" * 60)
    logger.info("📊 Cleanup Summary:")
    logger.info(f"   Total books processed: {len(books)}")
    logger.info(f"   Books updated: {books_updated}")
    logger.info(f"   Books unchanged: {books_unchanged}")
    logger.info(f"   Invalid categories removed: {total_removed}")
    logger.info(f"   Valid categories kept: {total_kept}")
    logger.info("=" * 60)
    
    return True


def main():
    parser = argparse.ArgumentParser(description="MyBibliotheca Dev Script: Cleanup Invalid Categories")
    parser.add_argument('--dry-run', action='store_true', 
                        help='Show what would be changed without actually updating the database')
    parser.add_argument('--force', action='store_true', 
                        help='Bypass development mode check (use with caution!)')
    args = parser.parse_args()

    print("=" * 60)
    print("MyBibliotheca - Cleanup Invalid Categories (Dev Script)")
    print("=" * 60)

    if not check_dev_mode() and not args.force:
        logger.error("❌ ERROR: This script can only be run in development mode!")
        print("\nTo enable development mode, set one of:")
        print("  - FLASK_ENV=development")
        print("  - FLASK_DEBUG=1")
        print("  - MYBIBLIOTHECA_DEBUG=1")
        print("  - DEBUG=True in config.py")
        sys.exit(1)
    
    if args.force:
        logger.warning("⚠️  WARNING: Running with --force flag!")
        logger.warning("   This bypasses development mode check.")
    
    logger.info("✅ Development mode detected")

    if args.dry_run:
        logger.info("🔍 DRY RUN MODE: No changes will be made to the database")
    
    logger.info("📊 Checking database...")
    book_count = get_book_count()

    if book_count == -1:
        logger.error("❌ Failed to connect to database or get book count. Exiting.")
        sys.exit(1)
    elif book_count == 0:
        logger.info("✅ No books found in the database. Nothing to cleanup.")
        sys.exit(0)
    
    logger.info(f"📚 Found {book_count} books in the database.")
    
    if args.dry_run:
        confirmation = input("Type 'YES' to proceed with dry run: ")
        confirmation_ok = confirmation.strip().upper() == 'YES'
    else:
        confirmation = input("Type 'CLEANUP CATEGORIES' to confirm cleanup: ")
        confirmation_ok = confirmation.strip().upper() == 'CLEANUP CATEGORIES'

    if confirmation_ok:
        logger.info("🔄 Starting category cleanup...")
        try:
            # Create app context to ensure database connections work
            app = create_app()
            with app.app_context():
                logger.info("📋 Calling cleanup function...")
                result = run_async(cleanup_all_categories_async(dry_run=args.dry_run))
                logger.info(f"✅ Category cleanup process completed. Result: {result}")
        except Exception as e:
            logger.error(f"❌ An unexpected error occurred during cleanup: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        logger.info("🚫 Cleanup cancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()

