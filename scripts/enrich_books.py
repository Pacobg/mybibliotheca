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
                        
                        # Only include books with title and author
                        if book_dict['title'] and book_dict['author'] != 'Unknown':
                            # Check if it's a Bulgarian book
                            # Bulgarian books have Cyrillic characters in title OR language='bg'
                            has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in title)
                            is_bg_language = book_dict.get('language') == 'bg'
                            
                            if has_cyrillic or is_bg_language:
                                books.append(book_dict)
                                logger.debug(f"✅ Added Bulgarian book: {title}")
                            else:
                                logger.debug(f"⏭️  Skipping non-Bulgarian book: {title} (language: {language})")
            
            logger.info(f"✅ Found {len(books)} books to enrich")
            return books
            
        except Exception as e:
            logger.error(f"❌ Error querying database: {e}", exc_info=True)
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
                if enriched.get('description') and (
                    not book.get('description') or 
                    len(enriched['description']) > len(book.get('description', ''))
                ):
                    updates['description'] = enriched['description']
                
                # Update cover_url if missing
                if enriched.get('cover_url') and not book.get('cover_url'):
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
                
                # Save to database using book service
                if updates:
                    try:
                        # Use the async method from book service
                        updated_book = await book_service.update_book(
                            book['id'],
                            updates=updates,
                            user_id='system'  # System user for enrichment
                        )
                        if updated_book:
                            saved_count += 1
                            logger.debug(f"✅ Saved: {book['title']}")
                        else:
                            logger.warning(f"⚠️  Failed to save: {book['title']}")
                    except Exception as e:
                        logger.error(f"❌ Error updating book {book['id']}: {e}")
                
                # Handle publisher separately (it's a relationship, not a property)
                if publisher_name and not has_publisher:
                    try:
                        # Use repository method to create publisher relationship
                        await self.book_repo._create_publisher_relationship(book['id'], publisher_name)
                        logger.debug(f"✅ Added publisher: {publisher_name} for {book['title']}")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to add publisher for {book['title']}: {e}")
                
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
    
    args = parser.parse_args()
    
    # Set environment variable for quality threshold
    os.environ['AI_ENRICHMENT_MIN_QUALITY'] = str(args.quality_min)
    
    # Run command
    command = EnrichmentCommand(args)
    exit_code = asyncio.run(command.run())
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

