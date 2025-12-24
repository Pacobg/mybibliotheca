"""
Book Enrichment Service
Orchestrates metadata enrichment using multiple AI providers

Author: MyBibliotheca Team
Created: 2025-12-23
"""

import os
import logging
import asyncio
from typing import Optional, Dict, List
from datetime import datetime

from .metadata_providers.perplexity import PerplexityEnricher

logger = logging.getLogger(__name__)


class EnrichmentService:
    """
    Orchestrates book metadata enrichment using AI web search
    
    Strategy:
    1. Try Perplexity (primary - best for web search)
    2. Fall back to OpenAI if needed (optional)
    3. Apply metadata to books
    4. Download cover images
    """
    
    def __init__(self):
        """Initialize enrichment service"""
        
        # Initialize Perplexity
        perplexity_key = os.getenv('PERPLEXITY_API_KEY')
        if perplexity_key:
            self.perplexity = PerplexityEnricher(api_key=perplexity_key)
            logger.info("✅ Perplexity enricher initialized")
        else:
            self.perplexity = None
            logger.warning("⚠️  PERPLEXITY_API_KEY not set - enrichment disabled")
        
        # Configuration
        self.min_quality_score = float(os.getenv('AI_ENRICHMENT_MIN_QUALITY', '0.7'))
        self.rate_limit_delay = float(os.getenv('AI_ENRICHMENT_RATE_LIMIT', '1.0'))
        self.download_covers = os.getenv('AI_COVER_DOWNLOAD', 'true').lower() == 'true'
        
        logger.info(f"⚙️  Config: min_quality={self.min_quality_score}, "
                   f"rate_limit={self.rate_limit_delay}s, "
                   f"download_covers={self.download_covers}")
    
    async def enrich_single_book(
        self, 
        book_data: Dict,
        force: bool = False
    ) -> Optional[Dict]:
        """
        Enrich a single book with AI metadata
        
        Args:
            book_data: Dictionary with book data (must have 'title' and 'author')
            force: Force enrichment even if book already has data
            
        Returns:
            Enriched metadata dictionary or None
        """
        
        if not self.perplexity:
            logger.error("Perplexity not initialized - cannot enrich")
            return None
        
        title = book_data.get('title')
        author = book_data.get('author') or book_data.get('author', 'Unknown')
        
        if not title:
            logger.error("Missing title - cannot enrich")
            return None
        
        # If author is Unknown or missing, try to enrich anyway (AI might find it)
        if not author or author == 'Unknown':
            logger.info(f"⚠️  Book '{title}' has no author - will try to find it via AI")
            author = ''  # Empty author - AI will try to find it
        
        # Check if book already has good data (unless force)
        if not force and self._has_sufficient_data(book_data, require_cover=require_cover):
            logger.info(f"⏭️  Skipping {title} - already has sufficient data")
            return None
        
        try:
            # Try Perplexity enrichment
            logger.info(f"🔍 Enriching: {title} - {author}")
            
            metadata = await self.perplexity.enrich_book(
                title=title,
                author=author,
                existing_data=book_data
            )
            
            if not metadata:
                logger.warning(f"❌ No metadata found for: {title}")
                return None
            
            # Check quality
            quality = metadata.get('quality_score', 0)
            if quality < self.min_quality_score:
                logger.warning(
                    f"⚠️  Low quality metadata for {title}: {quality:.2f} "
                    f"< {self.min_quality_score}"
                )
                return None
            
            # Try to find cover if not in metadata
            if not metadata.get('cover_url') and self.download_covers:
                logger.info(f"🖼️  Searching for cover: {title}")
                isbn = book_data.get('isbn') or book_data.get('isbn13') or book_data.get('isbn10')
                cover_url = await self.perplexity.find_cover_image(
                    title=title,
                    author=author,
                    isbn=isbn
                )
                if cover_url:
                    metadata['cover_url'] = cover_url
            
            logger.info(f"✅ Enriched: {title} (quality: {quality:.2f})")
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Error enriching {title}: {e}", exc_info=True)
            return None
    
    async def enrich_batch(
        self, 
        books: List[Dict],
        force: bool = False,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """
        Enrich multiple books in batch
        
        Args:
            books: List of book dictionaries
            progress_callback: Optional callback for progress updates
                              Signature: callback(processed, total, current_book, metadata)
            
        Returns:
            Statistics dictionary
        """
        
        stats = {
            'total': len(books),
            'processed': 0,
            'enriched': 0,
            'failed': 0,
            'skipped': 0,
            'covers_found': 0,
            'descriptions_added': 0,
            'start_time': datetime.now(),
        }
        
        logger.info(f"📦 Starting batch enrichment: {len(books)} books")
        
        for i, book in enumerate(books, 1):
            try:
                # Enrich book (pass force flag and require_cover)
                metadata = await self.enrich_single_book(book, force=force, require_cover=require_cover)
                
                stats['processed'] += 1
                
                if metadata:
                    stats['enriched'] += 1
                    
                    if metadata.get('cover_url'):
                        stats['covers_found'] += 1
                    
                    if metadata.get('description'):
                        stats['descriptions_added'] += 1
                    
                    # Store metadata back in book
                    book['ai_metadata'] = metadata
                else:
                    stats['failed'] += 1
                
                # Progress callback
                if progress_callback:
                    await progress_callback(
                        processed=stats['processed'],
                        total=stats['total'],
                        current_book=book,
                        metadata=metadata
                    )
                
                # Rate limiting
                if i < len(books):  # Don't delay after last book
                    await asyncio.sleep(self.rate_limit_delay)
                
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
                stats['failed'] += 1
        
        # Final statistics
        stats['end_time'] = datetime.now()
        stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds()
        stats['success_rate'] = (
            stats['enriched'] / stats['total'] * 100 
            if stats['total'] > 0 else 0
        )
        
        logger.info(f"✅ Batch enrichment complete!")
        logger.info(f"   Processed: {stats['processed']}/{stats['total']}")
        logger.info(f"   Enriched: {stats['enriched']} ({stats['success_rate']:.1f}%)")
        logger.info(f"   Covers found: {stats['covers_found']}")
        logger.info(f"   Duration: {stats['duration']:.1f}s")
        
        return stats
    
    def _has_sufficient_data(self, book_data: Dict, require_cover: bool = False) -> bool:
        """
        Check if book already has sufficient metadata
        
        Args:
            book_data: Book data dictionary
            require_cover: If True, book must have a valid cover URL to be considered sufficient
            
        Returns:
            True if book has enough data, False otherwise
        """
        
        # Check for critical fields
        has_description = bool(
            book_data.get('description') and 
            len(book_data.get('description', '')) > 100
        )
        
        # Check cover - must be a valid URL (starts with http/https), not just a local path
        cover_url = book_data.get('cover') or book_data.get('cover_url') or ''
        has_cover = bool(cover_url and (cover_url.startswith('http://') or cover_url.startswith('https://')))
        
        has_publisher = bool(book_data.get('publisher'))
        has_isbn = bool(book_data.get('isbn') or book_data.get('isbn13') or book_data.get('isbn10'))
        
        # If cover is required (e.g., --no-cover-only mode), don't skip if missing valid cover
        if require_cover and not has_cover:
            return False
        
        # For Bulgarian books, cover is critical - don't skip if missing cover
        title = book_data.get('title', '')
        is_bulgarian = any('\u0400' <= char <= '\u04FF' for char in title) or book_data.get('language') == 'bg'
        
        if is_bulgarian:
            # Bulgarian books MUST have cover - it's critical
            if not has_cover:
                return False
            # Need at least 3 out of 4 including cover
            score = sum([has_description, has_cover, has_publisher, has_isbn])
            return score >= 3
        else:
            # For non-Bulgarian books, need at least 3 out of 4
            score = sum([has_description, has_cover, has_publisher, has_isbn])
            return score >= 3
    
    def merge_metadata_into_book(
        self, 
        book_data: Dict, 
        ai_metadata: Dict
    ) -> Dict:
        """
        Merge AI metadata into book data
        
        Strategy: Prefer AI data for missing fields, but be conservative
        
        Args:
            book_data: Existing book data
            ai_metadata: AI-enriched metadata
            
        Returns:
            Merged book data
        """
        
        merged = book_data.copy()
        
        # Title - use AI if more complete
        if ai_metadata.get('title'):
            ai_title = ai_metadata['title']
            if ai_metadata.get('subtitle'):
                ai_title += f": {ai_metadata['subtitle']}"
            
            # Use AI title if longer/better
            if len(ai_title) > len(merged.get('title', '')):
                merged['title'] = ai_title
        
        # Author - prefer existing (already validated)
        if not merged.get('author') and ai_metadata.get('author'):
            merged['author'] = ai_metadata['author']
        
        # Description - use AI if better (prefer Bulgarian descriptions)
        if ai_metadata.get('description'):
            ai_desc = ai_metadata['description']
            existing_desc = merged.get('description', '')
            
            # Check if existing description is in English (has Latin chars but no Cyrillic)
            existing_is_english = (
                existing_desc and 
                any(c.isalpha() and ord(c) < 128 for c in existing_desc) and
                not any('\u0400' <= char <= '\u04FF' for char in existing_desc)
            )
            
            # Check if AI description is in Bulgarian (has Cyrillic)
            ai_is_bulgarian = any('\u0400' <= char <= '\u04FF' for char in ai_desc)
            
            # Use AI description if:
            # 1. No existing description, OR
            # 2. Existing is English and AI is Bulgarian (prefer Bulgarian), OR
            # 3. AI description is significantly longer (50+ chars)
            if (not existing_desc or 
                (existing_is_english and ai_is_bulgarian) or 
                len(ai_desc) > len(existing_desc) + 50):
                merged['description'] = ai_desc
        
        # Cover - always prefer AI if available
        if ai_metadata.get('cover_url'):
            merged['cover_url'] = ai_metadata['cover_url']
            merged['cover_source'] = 'ai_perplexity'
        
        # Publisher
        if not merged.get('publisher') and ai_metadata.get('publisher'):
            merged['publisher'] = ai_metadata['publisher']
        
        # Year -> published_date
        if ai_metadata.get('year'):
            year_str = str(ai_metadata['year'])
            if not merged.get('published_date'):
                # Try to parse year as date
                try:
                    from datetime import date
                    merged['published_date'] = date(int(year_str), 1, 1)
                except (ValueError, TypeError):
                    pass
        
        # ISBN
        if ai_metadata.get('isbn'):
            isbn = str(ai_metadata['isbn']).replace('-', '').replace(' ', '')
            if len(isbn) == 13:
                merged['isbn13'] = isbn
            elif len(isbn) == 10:
                merged['isbn10'] = isbn
            else:
                # Try to assign to isbn13 if no existing ISBN
                if not merged.get('isbn13') and not merged.get('isbn10'):
                    merged['isbn13'] = isbn
        
        # Pages -> page_count
        if ai_metadata.get('pages') and not merged.get('page_count'):
            try:
                merged['page_count'] = int(ai_metadata['pages'])
            except (ValueError, TypeError):
                pass
        
        # Genres/Categories - merge
        if ai_metadata.get('genres'):
            existing_genres = set(merged.get('raw_categories', []) or [])
            ai_genres = set(ai_metadata['genres'])
            merged['raw_categories'] = list(existing_genres | ai_genres)
        
        # Store AI metadata for reference
        merged['ai_enrichment'] = {
            'source': ai_metadata.get('enrichment_source'),
            'model': ai_metadata.get('enrichment_model'),
            'date': ai_metadata.get('enrichment_date'),
            'quality_score': ai_metadata.get('quality_score'),
            'sources': ai_metadata.get('sources', [])
        }
        
        return merged
    
    async def close(self):
        """Close all connections"""
        if self.perplexity:
            await self.perplexity.close()

