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
from datetime import datetime
from typing import List, Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.services.enrichment_service import EnrichmentService
from app.infrastructure.kuzu_repositories import KuzuBookRepository
from app.infrastructure.kuzu_graph import safe_execute_kuzu_query
from app.services import book_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('enrichment.log')
    ]
)

logger = logging.getLogger(__name__)


class EnrichmentCommand:
    """
    Management command for batch book enrichment
    """
    
    def __init__(self, args):
        """Initialize command with arguments"""
        self.args = args
        self.service = None
        self.book_repo = KuzuBookRepository()
        self.stats = {
            'start_time': datetime.now(),
            'books_checked': 0,
            'books_enriched': 0,
            'books_failed': 0,
            'covers_found': 0,
            'descriptions_added': 0,
        }
    
    async def run(self):
        """Execute enrichment command"""
        
        logger.info("="*60)
        logger.info("BOOK ENRICHMENT - AI Web Search")
        logger.info("="*60)
        
        # Initialize service
        self.service = EnrichmentService()
        
        # Check API keys
        if not os.getenv('PERPLEXITY_API_KEY'):
            logger.error("❌ PERPLEXITY_API_KEY not set!")
            logger.error("   Please add it to your .env file:")
            logger.error("   PERPLEXITY_API_KEY=pplx-xxxxxxxxxxxxx")
            return 1
        
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
        results = await self.service.enrich_batch(
            books=books,
            force=self.args.force,
            progress_callback=self._progress_callback
        )
        
        # Update statistics
        self.stats.update(results)
        self.stats['end_time'] = datetime.now()
        
        # Save enriched books (if not dry run)
        if not self.args.dry_run:
            saved = await self._save_enriched_books(books)
            logger.info(f"💾 Saved {saved} enriched books to database")
        
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
                
                # If --no-cover-only flag is set, only get books without covers
                if hasattr(self.args, 'no_cover_only') and self.args.no_cover_only:
                    query = """
                    MATCH (b:Book)
                    OPTIONAL MATCH (b)-[:PUBLISHED_BY]->(p:Publisher)
                    WHERE (b.cover_url IS NULL OR b.cover_url = '')
                    RETURN b.id as id, b.title as title, b.description as description,
                           b.cover_url as cover_url, p.name as publisher,
                           b.isbn13 as isbn13, b.isbn10 as isbn10,
                           b.page_count as page_count, b.published_date as published_date,
                           b.language as language
                    ORDER BY b.created_at DESC
                    """
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
                           b.language as language
                    ORDER BY b.created_at DESC
                    """
            
            if self.args.limit:
                query += f" LIMIT {self.args.limit}"
            
            # Execute query
            result = safe_execute_kuzu_query(query, {})
            
            books = []
            if result and hasattr(result, 'has_next'):
                while result.has_next():
                    row = result.get_next()
                    # Check if we have enough columns (9 for old query, 10 for new with language)
                    if len(row) >= 9:
                        book_id = row[0]
                        title = row[1] or ''
                        
                        # Get authors for this book
                        authors = await self.book_repo.get_book_authors(book_id)
                        author_names = [a.get('name', '') for a in authors if a.get('name')]
                        author = ', '.join(author_names) if author_names else 'Unknown'
                        
                        # Handle both old (9 columns) and new (10 columns) query formats
                        language = row[9] if len(row) > 9 else None
                        
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
                        }
                        
                        # Include books even if they don't have authors (we'll enrich them)
                        if book_dict['title']:
                            # If --no-cover-only is set, include all books (not just Bulgarian)
                            if hasattr(self.args, 'no_cover_only') and self.args.no_cover_only:
                                books.append(book_dict)
                                if book_dict['author'] == 'Unknown':
                                    logger.debug(f"✅ Added book without cover and author: {title}")
                                else:
                                    logger.debug(f"✅ Added book without cover: {title}")
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
        
        for book in books:
            if 'ai_metadata' not in book:
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
                    # Remove citation markers like [3][5][7][9] before saving
                    import re
                    description = re.sub(r'\[\d+\]', '', description)
                    # Clean up multiple spaces
                    description = re.sub(r'\s+', ' ', description).strip()
                    
                    existing_desc = book.get('description', '')
                    # Check if existing description has citations
                    has_citations = bool(re.search(r'\[\d+\]', existing_desc))
                    
                    # Update if:
                    # 1. No existing description, OR
                    # 2. Force flag is set, OR
                    # 3. Existing has citations (needs cleaning), OR
                    # 4. New description is significantly longer
                    if (not existing_desc or 
                        self.args.force or 
                        has_citations or 
                        len(description) > len(existing_desc) + 50):
                        updates['description'] = description
                        if has_citations:
                            logger.info(f"🧹 Cleaning description citations for: {book['title']}")
                
                # Update cover_url if missing or force update
                if enriched.get('cover_url'):
                    # Always update cover if AI found one (even if exists, might be better quality)
                    if not book.get('cover_url') or self.args.force:
                        updates['cover_url'] = enriched['cover_url']
                
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
                if updates:
                    try:
                        # Use book_service directly (not facade) for simpler updates
                        from app.services.kuzu_book_service import KuzuBookService
                        book_update_service = KuzuBookService(user_id='system')
                        
                        # Update book using the service's update_book method
                        updated_book = await book_update_service.update_book(book['id'], updates)
                        
                        if updated_book:
                            saved_count += 1
                            logger.info(f"✅ Saved: {book['title']}")
                            logger.debug(f"   Updated fields: {', '.join(updates.keys())}")
                        else:
                            logger.warning(f"⚠️  Failed to save: {book['title']}")
                    except Exception as e:
                        logger.error(f"❌ Error updating book {book['id']}: {e}", exc_info=True)
                
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
                
                # Normalize author one more time to be sure
                if ai_author:
                    import re
                    # If multiple authors, prefer Bulgarian/Cyrillic
                    if ',' in ai_author or ';' in ai_author:
                        authors_list = [a.strip() for a in re.split(r'[,;]', ai_author)]
                        cyrillic_authors = [a for a in authors_list if any('\u0400' <= char <= '\u04FF' for char in a)]
                        if cyrillic_authors:
                            ai_author = cyrillic_authors[0]
                        else:
                            ai_author = authors_list[0]
                
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
        
        if metadata:
            self.stats['books_enriched'] += 1
            
            quality = metadata.get('quality_score', 0)
            
            logger.info(
                f"[{processed}/{total}] ✅ {current_book['title']} "
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
                f"[{processed}/{total}] ❌ {current_book['title']} "
                f"- No metadata found"
            )
    
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

