#!/usr/bin/env python3
"""
Management Command: Enrich Missing Books
Batch enrichment of books missing metadata using AI

Usage:
    python scripts/enrich_books.py [options]

Options:
    --limit N          Limit enrichment to N books
    --force            Force re-enrichment of all books
    --dry-run          Show what would be done without making changes
    --quality-min F    Minimum quality score (default: 0.7)
    --no-cover-only    Only enrich books without covers
    -y, --yes          Skip confirmation prompt

Examples:
    # Enrich all books missing data
    python scripts/enrich_books.py
    
    # Enrich first 50 books
    python scripts/enrich_books.py --limit 50
    
    # Dry run to see what would be done
    python scripts/enrich_books.py --dry-run --limit 10

Author: MyBibliotheca Team
Created: 2025-12-23
"""

import os
import sys
import asyncio
import argparse
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Setup logging FIRST before any logger usage
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('enrichment.log')
    ]
)

logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
try:
    from dotenv import load_dotenv
    # Load .env from project root
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(env_path)
    logger.info(f"✅ Loaded .env from: {env_path}")
    # Verify PERPLEXITY_API_KEY is loaded
    perplexity_key = os.getenv('PERPLEXITY_API_KEY')
    if perplexity_key:
        logger.info(f"✅ PERPLEXITY_API_KEY found (length: {len(perplexity_key)})")
    else:
        logger.warning("⚠️  PERPLEXITY_API_KEY not found in .env file")
except ImportError:
    logger.warning("⚠️  python-dotenv not installed - environment variables may not load")
except Exception as e:
    logger.warning(f"⚠️  Error loading .env: {e}")

from app.services.enrichment_service import EnrichmentService
from app.infrastructure.kuzu_repositories import KuzuBookRepository
from app.infrastructure.kuzu_graph import safe_execute_kuzu_query
from app.services import book_service


class EnrichmentCommand:
    """
    Management command for batch book enrichment
    """
    
    def __init__(self, args):
        """Initialize command with arguments"""
        self.args = args
        self.service = None
        
        # Initialize book_repo with retry logic for lock conflicts
        max_retries = 5
        retry_delay = 2  # seconds
        self.book_repo = None
        
        for attempt in range(max_retries):
            try:
                self.book_repo = KuzuBookRepository()
                # Try to access safe_manager to trigger initialization
                _ = self.book_repo.safe_manager
                logger.info(f"✅ Successfully initialized KuzuBookRepository (attempt {attempt + 1})")
                break
            except RuntimeError as e:
                if "Could not set lock on file" in str(e):
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️  Database lock conflict (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay}s...")
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error(f"❌ Failed to acquire database lock after {max_retries} attempts")
                        logger.error("💡 Tip: Make sure Flask app is not running or wait a few seconds and try again")
                        raise
                else:
                    raise
            except Exception as e:
                logger.error(f"❌ Error initializing KuzuBookRepository: {e}")
                raise
        
        if self.book_repo is None:
            raise RuntimeError("Failed to initialize KuzuBookRepository after retries")
        
        self.stats = {
            'start_time': datetime.now(),
            'books_checked': 0,
            'books_enriched': 0,
            'books_failed': 0,
            'covers_found': 0,
            'descriptions_added': 0,
        }
        self.enriched_books_list = []  # Track enriched books
        self.skipped_books_list = []   # Track skipped books (already enriched)
    
    async def run(self):
        """Execute enrichment command"""
        
        logger.info("="*60)
        logger.info("BOOK ENRICHMENT - AI Web Search")
        logger.info("="*60)
        
        # Initialize service (auto-detects provider from settings)
        logger.info("🔧 Initializing EnrichmentService...")
        self.service = EnrichmentService(provider='auto')
        
        # Check if any provider is available
        if not self.service.perplexity and not self.service.openai_enricher:
            logger.error("❌ No enrichment providers available!")
            logger.error("   Options:")
            logger.error("   1. Set PERPLEXITY_API_KEY in .env (recommended - has web search)")
            logger.error("   2. Configure OpenAI/Ollama in Settings > AI Settings")
            logger.error("      (Note: OpenAI/Ollama cannot search web for covers)")
            return 1
        else:
            if self.service.perplexity:
                logger.info("✅ Perplexity enricher is ready")
            if self.service.openai_enricher:
                logger.info("✅ OpenAI/Ollama enricher is ready")
        
        logger.info(f"⚙️  Configuration:")
        logger.info(f"   Limit: {self.args.limit or 'No limit'}")
        logger.info(f"   Force: {self.args.force}")
        logger.info(f"   Dry run: {self.args.dry_run}")
        logger.info(f"   Min quality: {self.args.quality_min}")
        if hasattr(self.args, 'no_cover_only') and self.args.no_cover_only:
            logger.info(f"   No cover only: True (only books without covers)")
        
        # Get books to enrich
        books = await self._get_books_to_enrich()
        
        if not books:
            logger.info("✅ No books need enrichment!")
            return 0
        
        logger.info(f"\n📚 Found {len(books)} books to enrich")
        
        if self.args.dry_run:
            logger.info("\n🔍 DRY RUN - showing first 10 books:")
            for i, book in enumerate(books[:10], 1):
                logger.info(f"   {i}. {book['title']} - {book.get('author', 'Unknown')}")
                missing = []
                if not book.get('description'):
                    missing.append('description')
                if not book.get('cover_url'):
                    missing.append('cover')
                if not book.get('publisher'):
                    missing.append('publisher')
                if not book.get('isbn13') and not book.get('isbn10'):
                    missing.append('isbn')
                logger.info(f"      Missing: {', '.join(missing) or 'none'}")
            
            logger.info(f"\n⚠️  DRY RUN MODE - No changes made")
            return 0
        
        # Confirm with user
        if not self.args.yes:
            response = input(f"\n❓ Enrich {len(books)} books? [y/N]: ")
            if response.lower() != 'y':
                logger.info("❌ Cancelled by user")
                return 0
        
        # Run enrichment
        logger.info(f"\n🚀 Starting enrichment...")
        logger.info(f"   Estimated time: ~{len(books) * 2 / 60:.1f} minutes")
        logger.info(f"   Estimated cost: ~${len(books) * 0.0008:.2f}")
        
        # Enrich books
        require_cover = hasattr(self.args, 'no_cover_only') and self.args.no_cover_only
        results = await self.service.enrich_batch(
            books=books,
            force=self.args.force,
            require_cover=require_cover,
            progress_callback=self._progress_callback
        )
        
        # Update statistics
        self.stats.update(results)
        self.stats['end_time'] = datetime.now()
        
        # Save enriched books (if not dry run)
        if not self.args.dry_run:
            saved = await self._save_enriched_books(books)
            logger.info(f"💾 Saved {saved} enriched books to database")
            
            # Update enrichment status file with enriched/skipped books
            try:
                enrichment_status_file = Path('data/enrichment_status.json')
                if enrichment_status_file.exists():
                    with open(enrichment_status_file, 'r') as f:
                        status = json.load(f)
                    
                    # Add enriched and skipped books to status
                    if 'enriched_books' not in status:
                        status['enriched_books'] = []
                    if 'skipped_books' not in status:
                        status['skipped_books'] = []
                    
                    status['enriched_books'].extend(self.enriched_books_list)
                    status['skipped_books'].extend(self.skipped_books_list)
                    status['processed'] = self.stats['books_checked']
                    status['enriched'] = self.stats['books_enriched']
                    status['failed'] = self.stats['books_failed']
                    
                    with open(enrichment_status_file, 'w') as f:
                        json.dump(status, f, indent=2)
                    
                    logger.info(f"📊 Tracked {len(self.enriched_books_list)} enriched and {len(self.skipped_books_list)} skipped books")
            except Exception as e:
                logger.warning(f"Could not update enrichment status file: {e}")
        
        # Show final report
        self._show_report()
        
        # Cleanup
        await self.service.close()
        
        return 0
    
    async def _get_books_to_enrich(self) -> List[Dict]:
        """
        Get list of books that need enrichment from KuzuDB
        
        Returns:
            List of book dictionaries
        """
        
        logger.info("📖 Querying database for books...")
        
        try:
            # Handle specific book requests
            if self.args.book_id:
                return await self._get_book_by_id(self.args.book_id)
            elif self.args.book_title:
                return await self._get_book_by_title(self.args.book_title)
            
            # Build query to find books missing metadata
            # Note: publisher is a relationship, not a property, so we check for PUBLISHED_BY relationship
            if self.args.force:
                # Force: get all books
                query = """
                MATCH (b:Book)
                OPTIONAL MATCH (b)-[:PUBLISHED_BY]->(p:Publisher)
                RETURN b.id as id, b.title as title, b.description as description,
                       b.cover_url as cover_url, p.name as publisher,
                       b.isbn13 as isbn13, b.isbn10 as isbn10,
                       b.page_count as page_count, b.published_date as published_date
                ORDER BY b.created_at DESC
                """
            else:
                # Get books missing critical metadata
                # Check for publisher relationship existence
                # Note: Filter for Bulgarian books happens in Python after query
                
                # If --no-cover-only flag is set, only get books without valid cover URLs
                if hasattr(self.args, 'no_cover_only') and self.args.no_cover_only:
                    # Query for ALL books, then filter in Python (KuzuDB WHERE filtering is unreliable)
                    # Python code will filter out books with valid http/https cover URLs
                    query = """
                    MATCH (b:Book)
                    OPTIONAL MATCH (b)-[:PUBLISHED_BY]->(p:Publisher)
                    RETURN b.id as id, b.title as title, b.description as description,
                           b.cover_url as cover_url, p.name as publisher,
                           b.isbn13 as isbn13, b.isbn10 as isbn10,
                           b.page_count as page_count, b.published_date as published_date,
                           b.language as language, b.custom_metadata as custom_metadata
                    ORDER BY b.created_at DESC
                    """
                    logger.info("🔍 [_get_books_to_enrich] Querying for ALL books - will filter books WITHOUT valid cover URLs in Python")
                else:
                    query = """
                    MATCH (b:Book)
                    OPTIONAL MATCH (b)-[:PUBLISHED_BY]->(p:Publisher)
                    WHERE (b.description IS NULL OR b.description = '')
                       OR (b.cover_url IS NULL OR b.cover_url = '')
                       OR (p IS NULL)
                       OR ((b.isbn13 IS NULL OR b.isbn13 = '') AND (b.isbn10 IS NULL OR b.isbn10 = ''))
                    RETURN b.id as id, b.title as title, b.description as description,
                           b.cover_url as cover_url, p.name as publisher,
                           b.isbn13 as isbn13, b.isbn10 as isbn10,
                           b.page_count as page_count, b.published_date as published_date,
                           b.language as language, b.custom_metadata as custom_metadata
                    ORDER BY b.created_at DESC
                    """
            
            if self.args.limit:
                query += f" LIMIT {self.args.limit}"
            
            # Execute query
            logger.info(f"🔍 [_get_books_to_enrich] Executing query...")
            result = safe_execute_kuzu_query(query, {})
            
            books = []
            books_checked = 0
            books_with_valid_cover = 0
            books_without_valid_cover = 0
            
            if result and hasattr(result, 'has_next'):
                logger.info(f"🔍 [_get_books_to_enrich] Query returned results, processing...")
                while result.has_next():
                    row = result.get_next()
                    books_checked += 1
                    # Check if we have enough columns (9 for old query, 10 for new with language)
                    if len(row) >= 9:
                        book_id = row[0]
                        title = row[1] or ''
                        
                        # Get authors for this book
                        authors = await self.book_repo.get_book_authors(book_id)
                        author_names = [a.get('name', '') for a in authors if a.get('name')]
                        author = ', '.join(author_names) if author_names else 'Unknown'
                        
                        # Handle both old (9 columns) and new (10+ columns) query formats
                        language = row[9] if len(row) > 9 else None
                        custom_metadata_raw = row[10] if len(row) > 10 else None
                        
                        # Parse custom_metadata to check enrichment tracking
                        custom_metadata = {}
                        if custom_metadata_raw:
                            try:
                                custom_metadata = json.loads(custom_metadata_raw) if isinstance(custom_metadata_raw, str) else custom_metadata_raw
                            except:
                                custom_metadata = {}
                        
                        # Check if book was recently enriched (within 24 hours) - skip if so
                        last_enriched_at = custom_metadata.get('last_enriched_at')
                        if last_enriched_at:
                            try:
                                enriched_time = datetime.fromisoformat(last_enriched_at.replace('Z', '+00:00'))
                                if datetime.now(enriched_time.tzinfo) - enriched_time < timedelta(hours=24):
                                    logger.info(f"⏭️  Skipping {title} - enriched recently ({last_enriched_at})")
                                    # Track skipped book
                                    self.skipped_books_list.append({
                                        'title': title,
                                        'id': book_id,
                                        'reason': f'Already enriched at {last_enriched_at}',
                                        'skipped_at': datetime.now().isoformat()
                                    })
                                    continue
                            except Exception as e:
                                logger.debug(f"Could not parse enrichment timestamp: {e}")
                        
                        book_dict = {
                            'id': book_id,
                            'title': title,
                            'author': author,
                            'description': row[2],
                            'cover_url': row[3],
                            'publisher': row[4],
                            'isbn13': row[5],
                            'isbn10': row[6],
                            'page_count': row[7],
                            'published_date': row[8],
                            'language': language,
                            'custom_metadata': custom_metadata,
                        }
                        
                        # Include books even if they don't have authors (we'll enrich them)
                        if book_dict['title']:
                            # If --no-cover-only is set, include all books (not just Bulgarian)
                            if hasattr(self.args, 'no_cover_only') and self.args.no_cover_only:
                                cover_url = book_dict.get('cover_url', '')
                                
                                # Check if cover URL is valid:
                                # 1. Must start with http:// or https://
                                # 2. Must end with image extension (.jpg, .jpeg, .png, .webp, .gif) OR
                                #    contain image extension in path (for URLs with query params)
                                # 3. Exclude cache URLs that don't end with proper extension (broken cache URLs)
                                has_valid_cover = False
                                if cover_url and (cover_url.startswith('http://') or cover_url.startswith('https://')):
                                    cover_url_lower = cover_url.lower()
                                    image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
                                    
                                    # Check if URL ends with image extension
                                    ends_with_extension = any(cover_url_lower.endswith(ext) for ext in image_extensions)
                                    
                                    # Check if URL contains image extension before query params
                                    contains_extension = any(f'{ext}?' in cover_url_lower or f'{ext}&' in cover_url_lower for ext in image_extensions)
                                    
                                    # Special case: cache URLs must end with extension to be valid
                                    # Broken cache URLs like "cache/926507dc7f..." are invalid
                                    # Also check for suspicious patterns like ISBN numbers in path (9783836555401)
                                    is_cache_url = '/cache/' in cover_url
                                    
                                    logger.info(f"🔍 [_get_books_to_enrich] '{title}': cover_url='{cover_url[:100]}...', is_cache_url={is_cache_url}, ends_with_extension={ends_with_extension}, contains_extension={contains_extension}")
                                    
                                    if is_cache_url:
                                        # Cache URLs must end with extension AND not contain suspicious patterns
                                        # Suspicious patterns: ISBN numbers (13 digits starting with 978 or 979) in path
                                        import re
                                        # Check for ISBN in path (can be between / or at end before extension)
                                        has_isbn_in_path = bool(re.search(r'/(978|979)\d{10}(/|\.)', cover_url))
                                        
                                        # Also check if path looks like ISBN instead of proper image filename
                                        # Proper cache URLs should have format: cache/HASH/path/to/image.jpg
                                        # Broken ones might have: cache/HASH/9/7/9783836555401.jpg
                                        path_after_cache = cover_url.split('/cache/')[-1] if '/cache/' in cover_url else ''
                                        # Remove extension from last segment for checking
                                        path_segments = [s for s in path_after_cache.split('/') if s]
                                        if path_segments:
                                            # Remove extension from last segment
                                            last_seg = path_segments[-1]
                                            for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
                                                if last_seg.lower().endswith(ext):
                                                    last_seg = last_seg[:-len(ext)]
                                                    break
                                            path_segments[-1] = last_seg
                                        
                                        # Check if path segments are mostly single digits (suspicious pattern like /9/7/9783836555401)
                                        # Valid paths should have meaningful names like /t/h/the_costume_history
                                        has_numeric_path = len(path_segments) > 2 and all(len(seg) <= 2 and seg.isdigit() for seg in path_segments[:-1])
                                        
                                        # Also check if filename itself is an ISBN (13 digits)
                                        filename_is_isbn = len(path_segments) > 0 and bool(re.match(r'^(978|979)\d{10}$', path_segments[-1]))
                                        
                                        has_valid_cover = ends_with_extension and not has_isbn_in_path and not has_numeric_path and not filename_is_isbn
                                        
                                        logger.info(f"🔍 [_get_books_to_enrich] Cache URL analysis: has_isbn_in_path={has_isbn_in_path}, has_numeric_path={has_numeric_path}, filename_is_isbn={filename_is_isbn}, path_segments={path_segments[-3:] if len(path_segments) >= 3 else path_segments}")
                                        
                                        if not has_valid_cover:
                                            logger.info(f"🔍 [_get_books_to_enrich] ❌ Cache URL invalid: '{cover_url[:100]}...' - ends_with_extension={ends_with_extension}, has_isbn_in_path={has_isbn_in_path}, has_numeric_path={has_numeric_path}, filename_is_isbn={filename_is_isbn} - marking as INVALID")
                                        else:
                                            logger.info(f"🔍 [_get_books_to_enrich] ✅ Cache URL valid: '{cover_url[:100]}...' - marking as VALID")
                                    else:
                                        # Non-cache URLs: check if ends with extension or contains it before query params
                                        has_valid_cover = ends_with_extension or contains_extension
                                        logger.info(f"🔍 [_get_books_to_enrich] Non-cache URL: has_valid_cover={has_valid_cover}")
                                        
                                        # If --no-cover-only is active, also check if URL is accessible
                                        if has_valid_cover and hasattr(self.args, 'no_cover_only') and self.args.no_cover_only:
                                            # Quick accessibility check (timeout 3 seconds)
                                            try:
                                                import httpx
                                                with httpx.Client(timeout=3.0, follow_redirects=True) as client:
                                                    response = client.head(cover_url)
                                                    if response.status_code == 200:
                                                        content_type = response.headers.get('content-type', '').lower()
                                                        if 'image' not in content_type:
                                                            has_valid_cover = False
                                                            logger.info(f"🔍 [_get_books_to_enrich] Non-cache URL returned non-image content-type: {content_type} - marking as INVALID")
                                                    elif response.status_code in [301, 302, 303, 307, 308]:
                                                        # Redirect - try GET to final URL
                                                        final_url = response.headers.get('location', cover_url)
                                                        get_response = client.get(final_url, timeout=3.0)
                                                        if get_response.status_code != 200:
                                                            has_valid_cover = False
                                                            logger.info(f"🔍 [_get_books_to_enrich] Non-cache URL redirect failed with status {get_response.status_code} - marking as INVALID")
                                                        else:
                                                            content_type = get_response.headers.get('content-type', '').lower()
                                                            if 'image' not in content_type:
                                                                has_valid_cover = False
                                                                logger.info(f"🔍 [_get_books_to_enrich] Non-cache URL redirect returned non-image content-type: {content_type} - marking as INVALID")
                                                    else:
                                                        has_valid_cover = False
                                                        logger.info(f"🔍 [_get_books_to_enrich] Non-cache URL returned status {response.status_code} - marking as INVALID")
                                            except Exception as e:
                                                # If accessibility check fails, still consider URL valid if it has image extension
                                                # (might be temporary network issue)
                                                logger.debug(f"🔍 [_get_books_to_enrich] Could not verify accessibility of {cover_url[:60]}...: {e} - assuming valid based on extension")
                                
                                # Double-check: only add books WITHOUT valid covers
                                if not has_valid_cover:
                                    books.append(book_dict)
                                    books_without_valid_cover += 1
                                    logger.info(f"✅ Added book without valid cover: {title} (cover_url='{cover_url[:60] if cover_url else 'None'}...')")
                                else:
                                    books_with_valid_cover += 1
                                    if books_checked <= 10:  # Log first 10 for debugging
                                        logger.info(f"⏭️  Skipping book with valid cover: {title} (cover_url='{cover_url[:60]}...')")
                                    elif books_checked == 11:
                                        logger.info(f"⏭️  ... (skipping remaining books with valid covers)")
                            else:
                                # Check if it's a Bulgarian book
                                # Bulgarian books have Cyrillic characters in title OR language='bg'
                                has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in title)
                                is_bg_language = book_dict.get('language') == 'bg'
                                
                                if has_cyrillic or is_bg_language:
                                    books.append(book_dict)
                                    if book_dict['author'] == 'Unknown':
                                        logger.debug(f"✅ Added Bulgarian book without author: {title}")
                                    else:
                                        logger.debug(f"✅ Added Bulgarian book: {title}")
                                else:
                                    logger.debug(f"⏭️  Skipping non-Bulgarian book: {title} (language: {language})")
            
            # Log statistics for --no-cover-only mode
            if hasattr(self.args, 'no_cover_only') and self.args.no_cover_only:
                logger.info(f"📊 Statistics: Checked {books_checked} books total")
                logger.info(f"📊 Statistics: {books_with_valid_cover} books WITH valid cover URLs (skipped)")
                logger.info(f"📊 Statistics: {books_without_valid_cover} books WITHOUT valid cover URLs (will enrich)")
                if len(books) == 0:
                    logger.warning("⚠️  No books found without valid cover URLs.")
                    if books_checked > 0:
                        logger.warning(f"⚠️  All {books_checked} checked books have valid http/https cover URLs.")
                    else:
                        logger.warning("⚠️  No books found in database (query returned 0 results).")
                    logger.info("💡 Tip: Use --force flag to force enrichment of all books, or add books without covers to the database.")
            
            logger.info(f"✅ Found {len(books)} books to enrich")
            return books
            
        except Exception as e:
            logger.error(f"❌ Error querying database: {e}", exc_info=True)
            return []
    
    async def _get_book_by_id(self, book_id: str) -> List[Dict]:
        """Get a specific book by ID for enrichment"""
        try:
            query = """
            MATCH (b:Book {id: $book_id})
            OPTIONAL MATCH (b)-[:PUBLISHED_BY]->(p:Publisher)
            RETURN b.id as id, b.title as title, b.description as description,
                   b.cover_url as cover_url, p.name as publisher,
                   b.isbn13 as isbn13, b.isbn10 as isbn10,
                   b.page_count as page_count, b.published_date as published_date,
                   b.language as language
            """
            
            result = safe_execute_kuzu_query(query, {"book_id": book_id})
            
            books = []
            if result and hasattr(result, 'has_next'):
                while result.has_next():
                    row = result.get_next()
                    if len(row) >= 10:
                        book_id_val = row[0]
                        title = row[1] or ''
                        
                        authors = await self.book_repo.get_book_authors(book_id_val)
                        author_names = [a.get('name', '') for a in authors if a.get('name')]
                        author = ', '.join(author_names) if author_names else 'Unknown'
                        
                        book_dict = {
                            'id': book_id_val,
                            'title': title,
                            'author': author,
                            'description': row[2],
                            'cover_url': row[3],
                            'publisher': row[4],
                            'isbn13': row[5],
                            'isbn10': row[6],
                            'page_count': row[7],
                            'published_date': row[8],
                            'language': row[9],
                        }
                        
                        # Include books even if they don't have authors (we'll enrich them)
                        if book_dict['title']:
                            books.append(book_dict)
                            if book_dict['author'] == 'Unknown':
                                logger.debug(f"📝 Book without author will be enriched: {title}")
            
            logger.info(f"✅ Found {len(books)} book(s) by ID")
            return books
        except Exception as e:
            logger.error(f"❌ Error getting book by ID: {e}", exc_info=True)
            return []
    
    async def _get_book_by_title(self, title_pattern: str) -> List[Dict]:
        """Get books by title pattern (partial match)"""
        try:
            logger.debug(f"🔍 Searching for book with title pattern: '{title_pattern}'")
            
            # Try multiple search patterns for better matching
            # Use case-insensitive search like other parts of the codebase
            query = """
            MATCH (b:Book)
            WHERE toLower(b.title) CONTAINS toLower($title_pattern)
               OR toLower(b.normalized_title) CONTAINS toLower($title_pattern)
               OR b.title = $title_pattern
               OR b.normalized_title = $title_pattern
            OPTIONAL MATCH (b)-[:PUBLISHED_BY]->(p:Publisher)
            RETURN b.id as id, b.title as title, b.description as description,
                   b.cover_url as cover_url, p.name as publisher,
                   b.isbn13 as isbn13, b.isbn10 as isbn10,
                   b.page_count as page_count, b.published_date as published_date,
                   b.language as language
            LIMIT 10
            """
            
            result = safe_execute_kuzu_query(query, {"title_pattern": title_pattern})
            logger.debug(f"🔍 Query returned result type: {type(result)}")
            
            # If no results, try a simpler query to see if book exists at all
            if not result or (hasattr(result, 'has_next') and not result.has_next()):
                logger.debug(f"🔍 No results from main query, trying simpler search...")
                simple_query = """
                MATCH (b:Book)
                RETURN b.id as id, b.title as title
                LIMIT 20
                """
                simple_result = safe_execute_kuzu_query(simple_query, {})
                if simple_result and hasattr(simple_result, 'has_next'):
                    logger.debug(f"🔍 Sample titles in database:")
                    count = 0
                    while simple_result.has_next() and count < 5:
                        row = simple_result.get_next()
                        if len(row) >= 2:
                            logger.debug(f"   - '{row[1]}'")
                            count += 1
            
            books = []
            if result and hasattr(result, 'has_next'):
                row_count = 0
                while result.has_next():
                    row = result.get_next()
                    row_count += 1
                    logger.debug(f"🔍 Processing row {row_count}: {row}")
                    if len(row) >= 10:
                        book_id = row[0]
                        title = row[1] or ''
                        
                        authors = await self.book_repo.get_book_authors(book_id)
                        author_names = [a.get('name', '') for a in authors if a.get('name')]
                        author = ', '.join(author_names) if author_names else 'Unknown'
                        
                        book_dict = {
                            'id': book_id,
                            'title': title,
                            'author': author,
                            'description': row[2],
                            'cover_url': row[3],
                            'publisher': row[4],
                            'isbn13': row[5],
                            'isbn10': row[6],
                            'page_count': row[7],
                            'published_date': row[8],
                            'language': row[9],
                        }
                        
                        # Include books even if they don't have authors (we'll enrich them)
                        if book_dict['title']:
                            books.append(book_dict)
                            if book_dict['author'] == 'Unknown':
                                logger.debug(f"📝 Book without author will be enriched: {title}")
            
            logger.info(f"✅ Found {len(books)} book(s) by title pattern: '{title_pattern}'")
            return books
        except Exception as e:
            logger.error(f"❌ Error getting book by title: {e}", exc_info=True)
            return []
    
    async def _save_enriched_books(self, books: List[Dict]) -> int:
        """
        Save enriched books back to database
        
        Args:
            books: List of enriched book dictionaries
            
        Returns:
            Number of books saved
        """
        
        saved_count = 0
        
        logger.info(f"🔍 [_save_enriched_books] Processing {len(books)} books for saving...")
        
        for book in books:
            book_title = book.get('title', 'Unknown')
            logger.info(f"🔍 [_save_enriched_books] Processing book: '{book_title}'")
            logger.info(f"🔍 [_save_enriched_books] Book keys: {list(book.keys())}")
            logger.info(f"🔍 [_save_enriched_books] Has ai_metadata: {'ai_metadata' in book}")
            
            if 'ai_metadata' not in book:
                logger.warning(f"⚠️  [_save_enriched_books] Skipping '{book_title}' - no ai_metadata found")
                continue
            
            try:
                # Merge AI metadata into book
                enriched = self.service.merge_metadata_into_book(
                    book_data=book,
                    ai_metadata=book['ai_metadata']
                )
                
                # Prepare update data
                updates = {}
                
                # Update description if missing or improved
                if enriched.get('description'):
                    description = enriched['description']
                    logger.info(f"🔍 [_save_enriched_books] Found description for '{book_title}': {description[:100]}...")
                    # Remove citation markers like [3][5][7][9] before saving
                    import re
                    description = re.sub(r'\[\d+\]', '', description)
                    # Clean up multiple spaces
                    description = re.sub(r'\s+', ' ', description).strip()
                    
                    existing_desc = book.get('description', '')
                    logger.info(f"🔍 [_save_enriched_books] Existing description for '{book_title}': {existing_desc[:100] if existing_desc else 'None'}...")
                    # Check if existing description has citations
                    has_citations = bool(re.search(r'\[\d+\]', existing_desc))
                    
                    # Check if description language matches title language
                    title = book.get('title', '') or enriched.get('title', '')
                    has_cyrillic_title = any('\u0400' <= char <= '\u04FF' for char in title)
                    desc_has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in description)
                    desc_matches_title = (has_cyrillic_title and desc_has_cyrillic) or (not has_cyrillic_title and not desc_has_cyrillic)
                    
                    existing_desc_has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in existing_desc) if existing_desc else False
                    existing_desc_matches_title = (has_cyrillic_title and existing_desc_has_cyrillic) or (not has_cyrillic_title and not existing_desc_has_cyrillic)
                    
                    logger.info(f"🔍 [_save_enriched_books] Language check for '{book_title}': title_has_cyrillic={has_cyrillic_title}, desc_has_cyrillic={desc_has_cyrillic}, desc_matches_title={desc_matches_title}, existing_desc_matches_title={existing_desc_matches_title}, has_citations={has_citations}, force={self.args.force}")
                    
                    # Update if:
                    # 1. No existing description, OR
                    # 2. Force flag is set, OR
                    # 3. Existing has citations (needs cleaning), OR
                    # 4. New description matches title language AND (existing doesn't match OR new is significantly longer)
                    should_update = (not existing_desc or 
                        self.args.force or 
                        has_citations or 
                        (desc_matches_title and (not existing_desc_matches_title or len(description) > len(existing_desc) + 50)))
                    
                    logger.info(f"🔍 [_save_enriched_books] Should update description for '{book_title}': {should_update}")
                    
                    if should_update:
                        if desc_matches_title or not existing_desc:
                            updates['description'] = description
                            logger.info(f"✅ [_save_enriched_books] Added description to updates for '{book_title}'")
                            if has_citations:
                                logger.info(f"🧹 Cleaning description citations for: {book['title']}")
                            if not desc_matches_title and existing_desc:
                                logger.warning(f"⚠️  Description language doesn't match title for '{book['title']}' - but updating anyway (no existing or force)")
                        else:
                            logger.warning(f"🚫 Rejecting description for '{book['title']}': language doesn't match title (title is {'Bulgarian' if has_cyrillic_title else 'English'}, desc is {'Bulgarian' if desc_has_cyrillic else 'English'})")
                else:
                    logger.info(f"🔍 [_save_enriched_books] No description in enriched data for '{book_title}'")
                
                # Update cover_url if missing or force update
                # Only update if new cover_url is a valid URL (http/https), not a local path
                if enriched.get('cover_url'):
                    new_cover_url = enriched['cover_url']
                    # Check if it's a valid URL (not a local path like /covers/...)
                    is_valid_url = new_cover_url.startswith('http://') or new_cover_url.startswith('https://')
                    current_cover_url = book.get('cover_url', '')
                    current_is_local = current_cover_url.startswith('/covers/') if current_cover_url else True
                    
                    # Check if current cover URL is valid (using same logic as _has_sufficient_data)
                    current_is_valid = False
                    if current_cover_url:
                        if current_cover_url.startswith('http://') or current_cover_url.startswith('https://'):
                            # Check if it ends with image extension or contains one before query params
                            image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
                            ends_with_extension = any(current_cover_url.lower().endswith(ext) for ext in image_extensions)
                            contains_extension = any(f'.{ext}' in current_cover_url.lower().split('?')[0] for ext in ['jpg', 'jpeg', 'png', 'webp', 'gif'])
                            
                            if '/cache/' in current_cover_url:
                                # Cache URLs must end with extension AND not contain suspicious patterns
                                import re
                                # Check for ISBN in path (can be between / or at end before extension)
                                has_isbn_in_path = bool(re.search(r'/(978|979)\d{10}(/|\.)', current_cover_url))
                                
                                # Also check if filename itself is an ISBN (13 digits)
                                path_after_cache = current_cover_url.split('/cache/')[-1] if '/cache/' in current_cover_url else ''
                                path_segments = [s for s in path_after_cache.split('/') if s]
                                if path_segments:
                                    # Remove extension from last segment
                                    last_seg = path_segments[-1]
                                    for ext in image_extensions:
                                        if last_seg.lower().endswith(ext):
                                            last_seg = last_seg[:-len(ext)]
                                            break
                                    filename_is_isbn = bool(re.match(r'^(978|979)\d{10}$', last_seg))
                                else:
                                    filename_is_isbn = False
                                
                                # Check if path segments are mostly single digits (suspicious pattern like /9/7/9783836555401)
                                has_numeric_path = len(path_segments) > 2 and all(len(seg) <= 2 and seg.isdigit() for seg in path_segments[:-1])
                                
                                current_is_valid = ends_with_extension and not has_isbn_in_path and not has_numeric_path and not filename_is_isbn
                            else:
                                # Non-cache URLs: check if ends with extension or contains it before query params
                                current_is_valid = ends_with_extension or contains_extension
                    
                    # Download and cache cover image locally instead of saving external URL
                    if is_valid_url:
                        # First, validate that the URL is accessible before trying to download
                        url_is_accessible = False
                        try:
                            import httpx
                            logger.info(f"🔍 Validating cover URL accessibility for '{book['title']}': {new_cover_url[:80]}...")
                            with httpx.Client(timeout=5.0, follow_redirects=True) as client:
                                response = client.head(new_cover_url)
                                if response.status_code == 200:
                                    content_type = response.headers.get('content-type', '').lower()
                                    if 'image' in content_type:
                                        url_is_accessible = True
                                        logger.info(f"✅ Cover URL is accessible: {new_cover_url[:80]}... (content-type: {content_type})")
                                    else:
                                        logger.warning(f"⚠️  Cover URL returned non-image content-type: {content_type}")
                                elif response.status_code in [301, 302, 303, 307, 308]:
                                    # Redirect - try GET to final URL
                                    final_url = response.headers.get('location', new_cover_url)
                                    get_response = client.get(final_url, timeout=5.0)
                                    if get_response.status_code == 200:
                                        content_type = get_response.headers.get('content-type', '').lower()
                                        if 'image' in content_type:
                                            url_is_accessible = True
                                            new_cover_url = final_url  # Use final URL after redirect
                                            logger.info(f"✅ Cover URL is accessible after redirect: {final_url[:80]}...")
                                    else:
                                        logger.warning(f"⚠️  Cover URL redirect failed with status {get_response.status_code}")
                                else:
                                    logger.warning(f"⚠️  Cover URL returned status {response.status_code}: {new_cover_url[:80]}...")
                        except Exception as e:
                            logger.warning(f"⚠️  Could not validate cover URL accessibility: {e}")
                            # If validation fails, assume URL might be accessible (might be temporary network issue)
                            # But we'll still try to download it
                            url_is_accessible = True  # Try anyway
                        
                        logger.info(f"🔍 [_save_enriched_books] Cover URL validation result for '{book['title']}': url_is_accessible={url_is_accessible}, new_cover_url='{new_cover_url[:80] if new_cover_url else 'None'}...'")
                        
                        # Only try to download if URL is accessible
                        if url_is_accessible:
                            try:
                                # Use process_image_from_url to download and cache the cover locally
                                # This will save the image to /covers/ directory and return a local path like /covers/uuid.jpg
                                from app.utils.image_processing import process_image_from_url
                                
                                # Create Flask app context for image processing
                                # Check if we're already in an app context
                                try:
                                    from flask import has_app_context, current_app
                                    if has_app_context():
                                        # Already in app context - use it directly
                                        logger.info(f"📥 Downloading cover image for '{book['title']}': {new_cover_url[:80]}...")
                                        local_cover_path = process_image_from_url(new_cover_url)
                                    else:
                                        # No app context - create one
                                        from app import create_app
                                        app = create_app()
                                        with app.app_context():
                                            logger.info(f"📥 Downloading cover image for '{book['title']}': {new_cover_url[:80]}...")
                                            local_cover_path = process_image_from_url(new_cover_url)
                                except RuntimeError:
                                    # No app context available - create one
                                    from app import create_app
                                    app = create_app()
                                    with app.app_context():
                                        logger.info(f"📥 Downloading cover image for '{book['title']}': {new_cover_url[:80]}...")
                                        local_cover_path = process_image_from_url(new_cover_url)
                                
                                if local_cover_path and local_cover_path.startswith('/covers/'):
                                    # Successfully downloaded and cached locally
                                    logger.info(f"✅ Cover downloaded and cached locally: {local_cover_path}")
                                    
                                    # Update if:
                                    # 1. No current cover, OR
                                    # 2. Current cover is invalid (local path or broken cache URL), OR
                                    # 3. Force flag is set
                                    if (not current_cover_url or not current_is_valid or self.args.force):
                                        updates['cover_url'] = local_cover_path
                                        logger.info(f"🖼️  Updating cover URL for: {book['title']} -> {local_cover_path}")
                                    elif current_cover_url and current_is_valid:
                                        logger.debug(f"⏭️  Skipping cover update for '{book['title']}' - already has valid URL: {current_cover_url[:80]}...")
                                else:
                                    logger.warning(f"⚠️  Failed to download cover image for '{book['title']}': {local_cover_path}")
                            except Exception as e:
                                logger.error(f"❌ Error downloading cover image for '{book['title']}': {e}")
                                # Don't fallback to inaccessible URL - just skip it
                        else:
                            logger.warning(f"⚠️  Skipping inaccessible cover URL for '{book['title']}': {new_cover_url[:80]}... (not accessible)")
                    else:
                        logger.warning(f"⚠️  Skipping invalid cover URL for '{book['title']}': {new_cover_url} (not http/https)")
                
                # Publisher is handled separately as a relationship
                publisher_name = enriched.get('publisher')
                has_publisher = False
                if publisher_name:
                    # Check if book already has a publisher
                    check_pub_query = """
                    MATCH (b:Book {id: $book_id})-[:PUBLISHED_BY]->(p:Publisher)
                    RETURN p.name as name
                    LIMIT 1
                    """
                    pub_result = safe_execute_kuzu_query(check_pub_query, {"book_id": book['id']})
                    if pub_result and hasattr(pub_result, 'has_next') and pub_result.has_next():
                        has_publisher = True
                
                # Update ISBN if missing
                if enriched.get('isbn13') and not book.get('isbn13'):
                    updates['isbn13'] = enriched['isbn13']
                if enriched.get('isbn10') and not book.get('isbn10'):
                    updates['isbn10'] = enriched['isbn10']
                
                # Update page_count if missing
                if enriched.get('page_count') and not book.get('page_count'):
                    updates['page_count'] = enriched['page_count']
                
                # Update published_date if missing
                if enriched.get('published_date') and not book.get('published_date'):
                    updates['published_date'] = enriched['published_date']
                
                # Update language to Bulgarian if book has Bulgarian title and author
                title = book.get('title', '') or enriched.get('title', '')
                ai_author = book.get('ai_metadata', {}).get('author') or enriched.get('author', '')
                
                # Check if title and author contain Cyrillic (Bulgarian)
                has_cyrillic_title = any('\u0400' <= char <= '\u04FF' for char in title)
                has_cyrillic_author = any('\u0400' <= char <= '\u04FF' for char in ai_author)
                
                if has_cyrillic_title and has_cyrillic_author:
                    # Book is Bulgarian - set language to 'bg'
                    current_language = book.get('language', '')
                    if current_language != 'bg':
                        updates['language'] = 'bg'
                        logger.info(f"🌍 Setting language to 'bg' for Bulgarian book: {title}")
                
                # Save to database using book service
                logger.info(f"🔍 [_save_enriched_books] Updates dictionary for '{book['title']}': {list(updates.keys())} (count: {len(updates)})")
                if updates:
                    try:
                        # Log what we're about to update
                        logger.info(f"📝 Updating book '{book['title']}' with fields: {list(updates.keys())}")
                        if 'cover_url' in updates:
                            logger.info(f"🖼️  Will update cover_url to: {updates['cover_url']}")
                        
                        # Use book_service directly (not facade) for simpler updates
                        from app.services.kuzu_book_service import KuzuBookService
                        book_update_service = KuzuBookService(user_id='system')
                        
                        # Update book using the service's update_book method
                        updated_book = await book_update_service.update_book(book['id'], updates)
                        
                        if updated_book:
                            saved_count += 1
                            logger.info(f"✅ Saved: {book['title']}")
                            logger.info(f"   Updated fields: {', '.join(updates.keys())}")
                            if 'cover_url' in updates:
                                logger.info(f"   Cover URL updated to: {updates['cover_url']}")
                            
                            # Track enriched book
                            self.enriched_books_list.append({
                                'title': book['title'],
                                'id': book['id'],
                                'updated_fields': list(updates.keys()),
                                'enriched_at': datetime.now().isoformat(),
                                'has_cover': 'cover_url' in updates
                            })
                            
                            # Track that this book was enriched
                            # Store enrichment timestamp in custom_metadata JSON field
                            try:
                                # Get current custom_metadata
                                get_metadata_query = """
                                MATCH (b:Book {id: $book_id})
                                RETURN b.custom_metadata as custom_metadata
                                """
                                result = safe_execute_kuzu_query(get_metadata_query, {"book_id": book['id']})
                                
                                custom_metadata = {}
                                if result and result.has_next():
                                    row = result.get_next()
                                    import json
                                    if row[0]:
                                        try:
                                            custom_metadata = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                                        except:
                                            custom_metadata = {}
                                
                                # Add enrichment tracking
                                custom_metadata['last_enriched_at'] = datetime.now().isoformat()
                                custom_metadata['enriched_by'] = 'ai_perplexity'
                                
                                # Update custom_metadata
                                update_tracking_query = """
                                MATCH (b:Book {id: $book_id})
                                SET b.custom_metadata = $custom_metadata
                                RETURN b.id
                                """
                                safe_execute_kuzu_query(
                                    update_tracking_query,
                                    {
                                        "book_id": book['id'],
                                        "custom_metadata": json.dumps(custom_metadata)
                                    }
                                )
                            except Exception as e:
                                # If tracking fails, log but don't fail the enrichment
                                logger.debug(f"Could not track enrichment for {book['title']}: {e}")
                        else:
                            logger.warning(f"⚠️  Failed to save: {book['title']}")
                    except Exception as e:
                        logger.error(f"❌ Error updating book {book['id']}: {e}", exc_info=True)
                else:
                    logger.warning(f"⚠️  [_save_enriched_books] No updates to save for '{book['title']}' - updates dictionary is empty")
                
                # Handle publisher separately (it's a relationship, not a property)
                if publisher_name and not has_publisher:
                    try:
                        # Use repository method to create publisher relationship
                        await self.book_repo._create_publisher_relationship(book['id'], publisher_name)
                        logger.debug(f"✅ Added publisher: {publisher_name} for {book['title']}")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to add publisher for {book['title']}: {e}")
                
                # Handle author update if AI found a normalized author
                # Get author directly from AI metadata (before merge) - this is already normalized
                ai_metadata = book.get('ai_metadata', {})
                ai_author = ai_metadata.get('author')
                
                # Debug: log what we found
                logger.debug(f"🔍 AI metadata author: {ai_author}")
                logger.debug(f"🔍 Enriched author: {enriched.get('author')}")
                
                if not ai_author:
                    # Fallback to enriched author
                    ai_author = enriched.get('author')
                
                # Normalize author based on book title language
                # Rule: If title is Bulgarian → use Bulgarian author, else use English author
                title = book.get('title', '') or enriched.get('title', '')
                has_cyrillic_title = any('\u0400' <= char <= '\u04FF' for char in title)
                
                if ai_author:
                    import re
                    # If multiple authors, choose based on title language
                    if ',' in ai_author or ';' in ai_author:
                        authors_list = [a.strip() for a in re.split(r'[,;]', ai_author)]
                        if has_cyrillic_title:
                            # Bulgarian title → prefer Bulgarian author
                            cyrillic_authors = [a for a in authors_list if any('\u0400' <= char <= '\u04FF' for char in a)]
                            if cyrillic_authors:
                                ai_author = cyrillic_authors[0]
                                logger.debug(f"✅ Using Bulgarian author for Bulgarian book: {ai_author}")
                            else:
                                # No Bulgarian author found, use first one
                                ai_author = authors_list[0]
                        else:
                            # English title → use English author (first one, prefer non-Cyrillic)
                            english_authors = [a for a in authors_list if not any('\u0400' <= char <= '\u04FF' for char in a)]
                            if english_authors:
                                ai_author = english_authors[0]
                                logger.debug(f"✅ Using English author for English book: {ai_author}")
                            else:
                                ai_author = authors_list[0]
                    else:
                        # Single author - check if it matches title language
                        has_cyrillic_author = any('\u0400' <= char <= '\u04FF' for char in ai_author)
                        if has_cyrillic_title and not has_cyrillic_author:
                            # Bulgarian title but English author - try to find Bulgarian version
                            logger.debug(f"⚠️  Bulgarian book '{title}' has English author '{ai_author}' - keeping for now")
                        elif not has_cyrillic_title and has_cyrillic_author:
                            # English title but Bulgarian author - skip update, keep original English author
                            logger.info(f"⚠️  Skipping Bulgarian author '{ai_author}' for English book '{title}' - keeping original author")
                            ai_author = None
                
                # Final check: Don't update author if title is English but AI returned Bulgarian
                if ai_author and not has_cyrillic_title:
                    has_cyrillic_author_final = any('\u0400' <= char <= '\u04FF' for char in ai_author)
                    if has_cyrillic_author_final:
                        logger.warning(f"🚫 Rejecting Bulgarian author '{ai_author}' for English book '{title}'")
                        ai_author = None
                
                if ai_author:
                    try:
                        # Get current authors
                        current_authors = await self.book_repo.get_book_authors(book['id'])
                        current_author_names = [a.get('name', '') for a in current_authors if a.get('name')]
                        
                        # Normalize current author names for comparison
                        current_normalized = []
                        for name in current_author_names:
                            # If name has multiple parts, try to normalize
                            if ',' in name or ';' in name:
                                parts = [a.strip() for a in re.split(r'[,;]', name)]
                                cyrillic_parts = [a for a in parts if any('\u0400' <= char <= '\u04FF' for char in a)]
                                if cyrillic_parts:
                                    current_normalized.append(cyrillic_parts[0])
                                else:
                                    current_normalized.append(parts[0])
                            else:
                                current_normalized.append(name)
                        
                        # Check if author needs to be updated
                        # Update if: multiple authors, or single author doesn't match AI author, or force flag
                        needs_update = (
                            len(current_author_names) != 1 or 
                            (len(current_normalized) == 1 and current_normalized[0] != ai_author) or
                            self.args.force
                        )
                        
                        if needs_update:
                            logger.info(f"📝 Updating authors from {current_author_names} to [{ai_author}]")
                            
                            # Remove all existing author relationships
                            delete_authors_query = """
                            MATCH (p:Person)-[r:AUTHORED]->(b:Book {id: $book_id})
                            DELETE r
                            """
                            safe_execute_kuzu_query(delete_authors_query, {"book_id": book['id']})
                            
                            # Add new author relationship
                            # First, find or create the person
                            person_query = """
                            MATCH (p:Person {name: $author_name})
                            RETURN p.id as id
                            LIMIT 1
                            """
                            person_result = safe_execute_kuzu_query(person_query, {"author_name": ai_author})
                            
                            person_id = None
                            if person_result and hasattr(person_result, 'has_next') and person_result.has_next():
                                row = person_result.get_next()
                                if len(row) > 0:
                                    person_id = row[0]
                            
                            if not person_id:
                                # Create new person
                                from app.domain.models import Person
                                from app.services.kuzu_person_service import KuzuPersonService
                                person_service = KuzuPersonService()
                                person = Person(name=ai_author)
                                created_person = await person_service.create_person(person)
                                if created_person:
                                    person_id = created_person.id
                            
                            if person_id:
                                # Create AUTHORED relationship
                                create_author_query = """
                                MATCH (p:Person {id: $person_id}), (b:Book {id: $book_id})
                                MERGE (p)-[r:AUTHORED {role: 'author', order_index: 0}]->(b)
                                RETURN r
                                """
                                safe_execute_kuzu_query(create_author_query, {
                                    "person_id": person_id,
                                    "book_id": book['id']
                                })
                                logger.info(f"✅ Updated author to: {ai_author}")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to update author for {book['title']}: {e}")
                
            except Exception as e:
                logger.error(f"❌ Error saving {book.get('title', 'unknown')}: {e}", exc_info=True)
        
        return saved_count
    
    async def _progress_callback(
        self, 
        processed: int, 
        total: int, 
        current_book: Dict,
        metadata: Optional[Dict]
    ):
        """
        Progress callback for batch enrichment
        
        Args:
            processed: Number of books processed
            total: Total number of books
            current_book: Current book being processed
            metadata: Enriched metadata (or None if failed)
        """
        
        # Update stats
        self.stats['books_checked'] = processed
        
        # Show progress
        progress_pct = processed / total * 100
        
        book_title = current_book.get('title', 'Unknown')
        logger.info(f"🔍 [_progress_callback] Book {processed}/{total}: '{book_title}', metadata={'found' if metadata else 'None'}")
        
        if metadata:
            self.stats['books_enriched'] += 1
            
            quality = metadata.get('quality_score', 0)
            
            logger.info(
                f"[{processed}/{total}] ✅ {book_title} "
                f"(quality: {quality:.2f})"
            )
            
            if metadata.get('cover_url'):
                self.stats['covers_found'] += 1
                logger.info(f"   🖼️  Cover found")
            
            if metadata.get('description'):
                self.stats['descriptions_added'] += 1
                logger.info(f"   📝 Description added")
        else:
            self.stats['books_failed'] += 1
            logger.warning(
                f"[{processed}/{total}] ❌ {book_title} "
                f"- No metadata found"
            )
            # Log book data to debug why enrichment failed
            logger.info(f"🔍 [_progress_callback] Book data: title='{book_title}', author='{current_book.get('author', 'Unknown')}', cover_url='{current_book.get('cover_url', 'None')}', description={'present' if current_book.get('description') else 'missing'}")
    
    def _show_report(self):
        """Show final enrichment report"""
        
        duration = (
            self.stats['end_time'] - self.stats['start_time']
        ).total_seconds()
        
        success_rate = (
            self.stats['books_enriched'] / self.stats['books_checked'] * 100
            if self.stats['books_checked'] > 0 else 0
        )
        
        logger.info("\n" + "="*60)
        logger.info("ENRICHMENT REPORT")
        logger.info("="*60)
        
        logger.info(f"📊 Statistics:")
        logger.info(f"   Books checked: {self.stats['books_checked']}")
        logger.info(f"   Books enriched: {self.stats['books_enriched']}")
        logger.info(f"   Books failed: {self.stats['books_failed']}")
        logger.info(f"   Success rate: {success_rate:.1f}%")
        
        logger.info(f"\n📝 Content:")
        logger.info(f"   Covers found: {self.stats['covers_found']}")
        logger.info(f"   Descriptions added: {self.stats['descriptions_added']}")
        
        logger.info(f"\n⏱️  Performance:")
        logger.info(f"   Duration: {duration:.1f}s")
        if duration > 0:
            logger.info(f"   Speed: {self.stats['books_checked'] / duration * 60:.1f} books/min")
        
        # Cost estimate
        cost = self.stats['books_checked'] * 0.0008
        logger.info(f"\n💰 Estimated cost: ${cost:.2f}")
        
        logger.info("="*60)


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description="Enrich books with AI-powered metadata search"
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit enrichment to N books'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-enrichment of all books (even those with data)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--quality-min',
        type=float,
        default=0.7,
        help='Minimum quality score (0.0-1.0, default: 0.7)'
    )
    
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    parser.add_argument(
        '--book-id',
        type=str,
        help='Enrich specific book by ID'
    )
    
    parser.add_argument(
        '--book-title',
        type=str,
        help='Enrich specific book by title (partial match)'
    )
    
    parser.add_argument(
        '--no-cover-only',
        action='store_true',
        help='Only enrich books without covers'
    )
    
    args = parser.parse_args()
    
    # Set environment variable for quality threshold
    os.environ['AI_ENRICHMENT_MIN_QUALITY'] = str(args.quality_min)
    
    # Run command
    command = EnrichmentCommand(args)
    exit_code = asyncio.run(command.run())
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

