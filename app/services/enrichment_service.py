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

# Try to import OpenAI enricher (optional)
try:
    from .metadata_providers.openai_enricher import OpenAIEnricher
    OPENAI_ENRICHER_AVAILABLE = True
except ImportError:
    OPENAI_ENRICHER_AVAILABLE = False
    logger.debug("OpenAI enricher not available")


class EnrichmentService:
    """
    Orchestrates book metadata enrichment using AI web search
    
    Strategy:
    1. Try Perplexity (primary - best for web search with real-time internet access)
    2. Fall back to OpenAI/Ollama from settings if Perplexity unavailable (limited - no web search)
    3. Apply metadata to books
    4. Download cover images
    """
    
    def __init__(self, provider: str = 'auto'):
        """
        Initialize enrichment service
        
        Args:
            provider: 'perplexity', 'openai', 'ollama', or 'auto' (default)
                    'auto' uses Perplexity if available, otherwise falls back to settings
        """
        self.provider = provider.lower()
        
        # Initialize Perplexity
        # Try from environment variable first, then from AI config
        perplexity_key = os.getenv('PERPLEXITY_API_KEY')
        if not perplexity_key:
            try:
                from app.admin import load_ai_config
                ai_config = load_ai_config()
                perplexity_key = ai_config.get('PERPLEXITY_API_KEY', '')
            except Exception:
                pass
        
        if perplexity_key and (self.provider == 'auto' or self.provider == 'perplexity'):
            perplexity_model = os.getenv('PERPLEXITY_MODEL') or None
            if not perplexity_model:
                try:
                    from app.admin import load_ai_config
                    ai_config = load_ai_config()
                    perplexity_model = ai_config.get('PERPLEXITY_MODEL', 'sonar-pro')
                except Exception:
                    perplexity_model = 'sonar-pro'
            self.perplexity = PerplexityEnricher(api_key=perplexity_key, model=perplexity_model)
            logger.info(f"✅ Perplexity enricher initialized with model: {perplexity_model}")
        else:
            self.perplexity = None
            if self.provider == 'perplexity':
                logger.warning("⚠️  PERPLEXITY_API_KEY not set - Perplexity enrichment disabled")
        
        # Initialize OpenAI/Ollama enricher (from settings)
        self.openai_enricher = None
        if OPENAI_ENRICHER_AVAILABLE and (self.provider == 'auto' or self.provider in ['openai', 'ollama']):
            try:
                # Load AI config from settings
                from app.admin import load_ai_config
                ai_config = load_ai_config()
                
                # Check if provider matches
                config_provider = ai_config.get('AI_PROVIDER', 'openai').lower()
                if self.provider == 'auto':
                    # Use OpenAI/Ollama only if Perplexity is not available
                    if not self.perplexity and config_provider in ['openai', 'ollama']:
                        self.openai_enricher = OpenAIEnricher(config=ai_config)
                        logger.info(f"✅ OpenAI/Ollama enricher initialized (provider: {config_provider})")
                elif self.provider in ['openai', 'ollama']:
                    if config_provider == self.provider:
                        self.openai_enricher = OpenAIEnricher(config=ai_config)
                        logger.info(f"✅ OpenAI/Ollama enricher initialized (provider: {config_provider})")
                    else:
                        logger.warning(f"⚠️  Requested provider '{self.provider}' but settings have '{config_provider}'")
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize OpenAI/Ollama enricher: {e}")
        
        if not self.perplexity and not self.openai_enricher:
            logger.warning("⚠️  No enrichment providers available - enrichment disabled")
        
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
        force: bool = False,
        require_cover: bool = False
    ) -> Optional[Dict]:
        """
        Enrich a single book with AI metadata
        
        Args:
            book_data: Dictionary with book data (must have 'title' and 'author')
            force: Force enrichment even if book already has data
            require_cover: If True, book must have valid cover URL to be considered sufficient
            
        Returns:
            Enriched metadata dictionary or None
        """
        
        title = book_data.get('title', 'Unknown')
        author = book_data.get('author', 'Unknown')
        cover_url = book_data.get('cover_url', 'None')
        has_description = bool(book_data.get('description'))
        
        logger.info(f"🔍 [ENRICH_SINGLE_BOOK] CALLED for '{title}'")
        logger.info(f"🔍 [ENRICH_SINGLE_BOOK] Book data: author='{author}', cover_url='{cover_url[:80] if cover_url != 'None' else 'None'}...', has_description={has_description}")
        logger.info(f"🔍 [ENRICH_SINGLE_BOOK] Parameters: force={force}, require_cover={require_cover}")
        
        # Check if any provider is available
        if not self.perplexity and not self.openai_enricher:
            logger.error("❌ [ENRICH_SINGLE_BOOK] No enrichment providers available - cannot enrich")
            return None
        
        if not title or title == 'Unknown':
            logger.error("❌ [ENRICH_SINGLE_BOOK] Missing title - cannot enrich")
            return None
        
        # If author is Unknown or missing, try to enrich anyway (AI might find it)
        if not author or author == 'Unknown':
            logger.info(f"⚠️  [ENRICH_SINGLE_BOOK] Book '{title}' has no author - will try to find it via AI")
            author = ''  # Empty author - AI will try to find it
        
        # Check if book already has good data (unless force)
        if not force:
            logger.info(f"🔍 [ENRICH_SINGLE_BOOK] Checking if '{title}' needs enrichment (force={force}, require_cover={require_cover})")
            has_sufficient = self._has_sufficient_data(book_data, require_cover=require_cover)
            logger.info(f"🔍 [ENRICH_SINGLE_BOOK] _has_sufficient_data returned: {has_sufficient} for '{title}'")
            if has_sufficient:
                logger.info(f"⏭️  [ENRICH_SINGLE_BOOK] Skipping {title} - already has sufficient data")
                return None
            else:
                logger.info(f"🔍 [ENRICH_SINGLE_BOOK] Book '{title}' needs enrichment (has_sufficient_data=False, require_cover={require_cover})")
        
        try:
            logger.info(f"🔍 Enriching: {title} - {author}")
            logger.info(f"🔍 Searching for: {title} - {author or ''}")
            
            # Check if providers are available
            if not self.perplexity and not self.openai_enricher:
                logger.error(f"❌ No enrichment providers available for {title}")
                return None
            
            if self.perplexity:
                logger.info(f"✅ Using Perplexity enricher (has web search)")
            elif self.openai_enricher:
                logger.info(f"⚠️  Using OpenAI/Ollama enricher (no web search)")
            
            # Try Perplexity first (has web search)
            metadata = None
            if self.perplexity:
                try:
                    logger.info(f"📡 Calling Perplexity API for: {title} by {author or 'unknown author'}")
                    metadata = await self.perplexity.enrich_book(
                        title=title,
                        author=author,
                        existing_data=book_data
                    )
                    if metadata:
                        logger.info(f"✅ Perplexity returned metadata for {title} (quality: {metadata.get('quality_score', 0):.2f})")
                    else:
                        logger.warning(f"⚠️  Perplexity returned None for {title} - no metadata found")
                except Exception as e:
                    logger.error(f"❌ Perplexity enrichment failed for {title}: {e}", exc_info=True)
            
            # Fall back to OpenAI/Ollama if Perplexity unavailable or failed
            if not metadata and self.openai_enricher:
                try:
                    logger.info(f"🔄 Trying OpenAI/Ollama enrichment (no web search)")
                    metadata = await self.openai_enricher.enrich_book(
                        title=title,
                        author=author,
                        existing_data=book_data
                    )
                    if metadata:
                        logger.info("✅ OpenAI/Ollama enrichment succeeded (limited - no web search)")
                except Exception as e:
                    logger.warning(f"OpenAI/Ollama enrichment failed: {e}")
            
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
                
                # Try Perplexity first (has web search)
                cover_url = None
                if self.perplexity:
                    try:
                        cover_url = await self.perplexity.find_cover_image(
                            title=title,
                            author=author,
                            isbn=isbn
                        )
                    except Exception as e:
                        logger.warning(f"Perplexity cover search failed: {e}")
                
                # OpenAI/Ollama cannot search for covers (no web search)
                if not cover_url and self.openai_enricher:
                    logger.debug("OpenAI/Ollama cannot search for covers (no web search capability)")
                
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
        require_cover: bool = False,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """
        Enrich multiple books in batch
        
        Args:
            books: List of book dictionaries
            force: Force enrichment even if book already has data
            require_cover: If True, books must have valid cover URL to be considered sufficient
            progress_callback: Optional callback for progress updates
                              Signature: callback(processed, total, current_book, metadata)
            
        Returns:
            Statistics dictionary
        """
        
        # Store require_cover flag for use in enrich_single_book
        self._require_cover = require_cover
        
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
                book_title = book.get('title', 'Unknown')
                logger.info(f"🔍 [enrich_batch] Processing book {i}/{len(books)}: '{book_title}' (force={force}, require_cover={require_cover})")
                
                # Enrich book (pass force flag and require_cover)
                metadata = await self.enrich_single_book(book, force=force, require_cover=require_cover)
                
                stats['processed'] += 1
                logger.info(f"🔍 [enrich_batch] Book {i}/{len(books)} '{book_title}': metadata={'found' if metadata else 'None'}")
                
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
        
        title = book_data.get('title', '')
        
        # Check for critical fields
        has_description = bool(
            book_data.get('description') and 
            len(book_data.get('description', '')) > 100
        )
        
        # Check cover - must be a valid URL (starts with http/https) AND ends with image extension
        cover_url = book_data.get('cover') or book_data.get('cover_url') or ''
        has_cover = False
        if cover_url and (cover_url.startswith('http://') or cover_url.startswith('https://')):
            # Check if URL ends with image extension or contains it in path
            cover_url_lower = cover_url.lower()
            image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
            # Check if URL ends with extension or contains it before query params
            if any(cover_url_lower.endswith(ext) or f'{ext}?' in cover_url_lower or f'{ext}&' in cover_url_lower for ext in image_extensions):
                # Additional check: exclude suspicious cache URLs that don't end with proper extension
                # These are often broken cache URLs like "cache/926507dc7f..."
                if not ('/cache/' in cover_url and not any(cover_url_lower.endswith(ext) for ext in image_extensions)):
                    has_cover = True
        
        has_publisher = bool(book_data.get('publisher'))
        has_isbn = bool(book_data.get('isbn') or book_data.get('isbn13') or book_data.get('isbn10'))
        
        logger.info(f"🔍 [_has_sufficient_data] Checking '{title}': require_cover={require_cover}, has_description={has_description}, has_cover={has_cover} (cover_url='{cover_url[:50] if cover_url else 'None'}...'), has_publisher={has_publisher}, has_isbn={has_isbn}")
        
        # If cover is required (e.g., --no-cover-only mode), only enrich books WITHOUT valid covers
        # If book has valid cover, skip it (it's sufficient)
        if require_cover:
            if has_cover:
                logger.info(f"🔍 [_has_sufficient_data] '{title}' has sufficient data: require_cover=True and has_cover=True - SKIPPING")
                return True  # Book has cover, skip it
            else:
                logger.info(f"🔍 [_has_sufficient_data] '{title}' needs enrichment: require_cover=True but has_cover=False - WILL ENRICH")
                return False  # Book needs cover, enrich it
        
        # For Bulgarian books, cover is critical - don't skip if missing cover
        is_bulgarian = any('\u0400' <= char <= '\u04FF' for char in title) or book_data.get('language') == 'bg'
        
        if is_bulgarian:
            # Bulgarian books MUST have cover - it's critical
            if not has_cover:
                logger.info(f"🔍 [_has_sufficient_data] '{title}' needs enrichment: Bulgarian book without cover")
                return False
            # Need at least 3 out of 4 including cover
            score = sum([has_description, has_cover, has_publisher, has_isbn])
            result = score >= 3
            logger.info(f"🔍 [_has_sufficient_data] '{title}' Bulgarian book score: {score}/4, sufficient={result}")
            return result
        else:
            # For non-Bulgarian books, need at least 3 out of 4
            score = sum([has_description, has_cover, has_publisher, has_isbn])
            result = score >= 3
            logger.info(f"🔍 [_has_sufficient_data] '{title}' Non-Bulgarian book score: {score}/4, sufficient={result}")
            return result
    
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
        
        # Description - use AI if better, matching book title language
        if ai_metadata.get('description'):
            ai_desc = ai_metadata['description']
            existing_desc = merged.get('description', '')
            
            # Check book title language
            title = merged.get('title', '') or ai_metadata.get('title', '')
            has_cyrillic_title = any('\u0400' <= char <= '\u04FF' for char in title)
            
            # Check if existing description matches title language
            existing_has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in existing_desc) if existing_desc else False
            existing_matches_title = (has_cyrillic_title and existing_has_cyrillic) or (not has_cyrillic_title and not existing_has_cyrillic)
            
            # Check if AI description matches title language
            ai_has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in ai_desc)
            ai_matches_title = (has_cyrillic_title and ai_has_cyrillic) or (not has_cyrillic_title and not ai_has_cyrillic)
            
            # Use AI description ONLY if it matches title language
            # Exception: if no existing description and AI doesn't match, still use it (better than nothing)
            if not existing_desc:
                # No existing description - use AI even if language doesn't match
                merged['description'] = ai_desc
                if not ai_matches_title:
                    logger.warning(f"⚠️  Using description that doesn't match title language for '{title}' (no existing description)")
            elif ai_matches_title:
                # AI description matches title language - use it if better
                if not existing_matches_title or len(ai_desc) > len(existing_desc) + 50:
                    merged['description'] = ai_desc
                    logger.debug(f"✅ Using description matching title language for '{title}'")
                else:
                    logger.debug(f"⏭️  Keeping existing description for '{title}' (AI not significantly better)")
            else:
                # AI description doesn't match title language - reject it
                logger.warning(f"🚫 Rejecting description that doesn't match title language for '{title}': AI is {'Bulgarian' if ai_has_cyrillic else 'English'}, title is {'Bulgarian' if has_cyrillic_title else 'English'}")
                # Keep existing description if it matches title language
                if existing_matches_title:
                    logger.debug(f"✅ Keeping existing description matching title language")
                elif not existing_desc:
                    # No existing description and AI doesn't match - still use it (better than nothing)
                    merged['description'] = ai_desc
                    logger.warning(f"⚠️  Using mismatched description for '{title}' (no better option)")
        
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

