"""
Perplexity AI Web Search Enricher
Използва Perplexity AI за търсене и извличане на metadata от интернет

Author: MyBibliotheca Team
Created: 2025-12-23
"""

import httpx
import json
import re
import logging
import os
from typing import Optional, Dict, List
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class PerplexityEnricher:
    """
    Use Perplexity AI for web-based metadata enrichment
    
    Perplexity specializes in web search + AI reasoning, making it ideal
    for finding accurate metadata about Bulgarian books from internet sources.
    """
    
    API_URL = "https://api.perplexity.ai/chat/completions"
    
    # Perplexity models (as of Dec 2024)
    # Sonar model family - see https://docs.perplexity.ai/getting-started/models
    MODEL_SONAR = "sonar"  # Fast, reliable answers with detailed research
    MODEL_SONAR_PRO = "sonar-pro"  # Smart problem-solving with real-time evidence
    MODEL_SONAR_DEEP_RESEARCH = "sonar-deep-research"  # Expert-level insights from hundreds of sources
    
    def __init__(self, api_key: str, model: str = None):
        """
        Initialize Perplexity enricher
        
        Args:
            api_key: Perplexity API key
            model: Model to use (default: sonar-online for web search)
        """
        self.api_key = api_key
        # Default to sonar-pro for best balance of quality and web search
        # All sonar models support web search
        self.model = model or os.getenv('PERPLEXITY_MODEL', 'sonar-pro')
        self.client = httpx.AsyncClient(timeout=30.0)
        
        logger.info(f"✅ PerplexityEnricher initialized with model: {self.model}")
    
    async def enrich_book(
        self, 
        title: str, 
        author: str,
        existing_data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Search web for book metadata using Perplexity
        
        Args:
            title: Book title
            author: Book author
            existing_data: Existing book data (optional, for better queries)
            
        Returns:
            Dictionary with enriched metadata or None if failed
        """
        
        try:
            logger.info(f"🔍 Searching for: {title} - {author}")
            
            # Build search query
            query = self._build_metadata_query(title, author, existing_data)
            
            # Execute search
            response = await self._search(query)
            
            if not response:
                logger.warning(f"❌ No response from Perplexity for: {title}")
                return None
            
            # Parse response
            metadata = self._parse_response(response, title, author)
            
            if metadata:
                logger.info(
                    f"✅ Found metadata for: {title} "
                    f"(quality: {metadata.get('quality_score', 0):.2f})"
                )
            else:
                logger.warning(f"⚠️  Could not parse metadata for: {title}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Error enriching {title}: {e}", exc_info=True)
            return None
    
    def _build_metadata_query(
        self, 
        title: str, 
        author: str,
        existing_data: Optional[Dict] = None
    ) -> str:
        """
        Build optimized search query for metadata
        """
        
        # Check if we have partial data to guide search
        isbn = existing_data.get('isbn') if existing_data else None
        if not isbn:
            isbn = existing_data.get('isbn13') if existing_data else None
        if not isbn:
            isbn = existing_data.get('isbn10') if existing_data else None
        publisher = existing_data.get('publisher') if existing_data else None
        
        # Check if book title contains Cyrillic (Bulgarian)
        has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in title)
        
        # Normalize author - if multiple authors, try to find the main one
        # For Bulgarian books, prefer Bulgarian name format
        import re
        author_normalized = author
        if ',' in author or ';' in author:
            # Multiple authors - try to extract main author
            authors_list = [a.strip() for a in re.split(r'[,;]', author)]
            # For Bulgarian books, prefer Cyrillic name
            cyrillic_authors = [a for a in authors_list if any('\u0400' <= char <= '\u04FF' for char in a)]
            if cyrillic_authors:
                author_normalized = cyrillic_authors[0]  # Use first Bulgarian name
            else:
                author_normalized = authors_list[0]  # Use first author
        
        # Build query - handle missing author
        if author_normalized and author_normalized.strip():
            query = f"""
Намери детайлна информация за българската книга:

ЗАГЛАВИЕ: {title}
АВТОР: {author_normalized}
"""
        else:
            # No author provided - AI should find it
            query = f"""
Намери детайлна информация за българската книга:

ЗАГЛАВИЕ: {title}

ВАЖНО: Ако знаеш автора на тази книга, включи го в отговора!
"""
        
        if isbn:
            query += f"ISBN: {isbn}\n"
        if publisher:
            query += f"ИЗДАТЕЛСТВО: {publisher}\n"
        
        query += """

ВАЖНО: Търся ИЗКЛЮЧИТЕЛНО БЪЛГАРСКОТО издание на тази книга!
- Ако книгата е превод, търси българския превод
- Ако книгата е оригинално българска, търси българското издание
- НЕ търси оригиналното издание на друг език!

ТЪРСЯ СЛЕДНАТА ИНФОРМАЦИЯ:

1. **Точно заглавие** на български (може да има подзаглавие)
2. **Автор** - ЕДИН основен автор на български (не английско!). Ако книгата е от Агата Кристи, авторът е "Агата Кристи" (не "Christie, Agatha" или други варианти!)
3. **Преводач** (ако книгата е превод)
4. **Издателство** - българско издателство
5. **Година на издаване** в България
6. **ISBN номер** (ISBN-10 или ISBN-13)
7. **Брой страници**
8. **Жанр/Категории** (2-4 категории)
9. **Описание** - 3-4 изречения на български за какво е книгата
10. **URL на корица** - директен линк към изображение (JPG/PNG)

ВАЖНО:
- Търся БЪЛГАРСКОТО издание, НЕ оригинала!
- Корицата трябва да е от българското издание
- Ако има няколко издания, предпочитай по-новото
- Проверявай в: chitanka.info, biblioman, ciela.com, helikon.bg

КРИТИЧНО ВАЖНО: ОТГОВОРИ САМО С ВАЛИДЕН JSON ОБЕКТ! Без markdown code blocks, без текст преди или след JSON-а!

JSON ФОРМАТ (задължително):
{{
    "title": "Точно заглавие",
    "subtitle": "Подзаглавие ако има",
    "author": "Име Фамилия",
    "translator": "Име на преводач ако има",
    "publisher": "Име на издателство",
    "year": "2024",
    "isbn": "978-954-xxx-xxx-x",
    "pages": 384,
    "genres": ["Жанр1", "Жанр2", "Жанр3"],
    "description": "Описание на български...",
    "cover_url": "https://direkten-url-kam-korica.jpg",
    "confidence": 0.95,
    "sources": ["url1", "url2"]
}}

ПРАВИЛА:
- ВИНАГИ включи "title" и "author" полетата (задължителни!)
- Ако НЕ НАМЕРИШ някое поле, използвай null (не празен string!)
- Не измисляй информация - само точни данни от надеждни източници!
- JSON-ът трябва да е валиден и да може да се parse-не директно с json.loads()!
"""
        
        return query
    
    async def _search(self, query: str) -> Optional[Dict]:
        """
        Execute Perplexity search
        
        Args:
            query: Search query
            
        Returns:
            API response dictionary or None
        """
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Build payload - some parameters may not be supported in all API versions
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Ти си експерт по българска литература и книжен пазар. "
                        "Намираш ТОЧНА информация за български книги от интернет. "
                        "Винаги цитираш източници и не измисляш данни. "
                        "Отговаряш САМО в JSON формат, без допълнителен текст."
                    )
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "temperature": 0.1,  # Very low for factual accuracy
            "max_tokens": 1500
        }
        
        # Add optional parameters only if they're supported
        # Note: return_citations and search_recency_filter may not be available in all API versions
        # Try without them first, then add if needed
        
        try:
            response = await self.client.post(
                self.API_URL,
                headers=headers,
                json=payload
            )
            
            # Log response details for debugging
            if response.status_code != 200:
                error_detail = response.text[:500] if hasattr(response, 'text') else 'No error details'
                logger.error(f"Perplexity API error {response.status_code}: {error_detail}")
                logger.debug(f"Request payload: {json.dumps(payload, ensure_ascii=False)[:500]}")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            error_detail = ""
            if hasattr(e.response, 'text'):
                error_detail = e.response.text[:500]
            logger.error(f"HTTP error calling Perplexity: {e}")
            logger.error(f"Response details: {error_detail}")
            logger.debug(f"Request payload: {json.dumps(payload, ensure_ascii=False)[:500]}")
            return None
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling Perplexity: {e}")
            return None
        except Exception as e:
            logger.error(f"Error calling Perplexity: {e}", exc_info=True)
            return None
    
    def _parse_response(
        self, 
        response: Dict, 
        title: str, 
        author: str
    ) -> Optional[Dict]:
        """
        Parse Perplexity response and extract metadata
        
        Args:
            response: Raw API response
            title: Original title (for fallback)
            author: Original author (for fallback)
            
        Returns:
            Structured metadata dictionary or None
        """
        
        try:
            # Extract AI response
            content = response['choices'][0]['message']['content']
            
            # Debug: log first 500 chars of response
            logger.debug(f"Raw API response (first 500 chars): {content[:500]}")
            
            # Get citations (source URLs) - may be in different places in response
            citations = []
            if 'citations' in response:
                citations = response.get('citations', [])
            elif 'choices' in response and len(response['choices']) > 0:
                # Citations might be in choice metadata
                choice = response['choices'][0]
                if 'citations' in choice:
                    citations = choice.get('citations', [])
                elif 'message' in choice and 'citations' in choice['message']:
                    citations = choice['message'].get('citations', [])
            
            # Try to parse as JSON
            metadata = self._extract_json(content)
            
            if not metadata:
                logger.warning("Could not extract JSON from response")
                logger.debug(f"Full response content: {content}")
                return None
            
            # Clean description - remove citation markers like [3][5][7][9]
            if metadata.get('description'):
                description = metadata['description']
                # Remove citation patterns like [1], [2][3], [1][2][3][4], etc.
                description = re.sub(r'\[\d+\]', '', description)
                # Clean up multiple spaces
                description = re.sub(r'\s+', ' ', description).strip()
                metadata['description'] = description
            
            # Debug: log parsed metadata
            logger.debug(f"Parsed metadata keys: {list(metadata.keys())}")
            logger.info(f"📋 Found metadata fields: {', '.join([k for k, v in metadata.items() if v])}")
            
            # If title is missing but we have content, try to extract it
            if not metadata.get('title') and title:
                # Use original title as fallback
                metadata['title'] = title
                logger.debug(f"Using original title as fallback: {title}")
            
            # Normalize author - ensure single main author
            if metadata.get('author'):
                author_from_ai = metadata['author']
                # If multiple authors separated by comma/semicolon, take the first/main one
                if ',' in author_from_ai or ';' in author_from_ai:
                    authors_list = [a.strip() for a in re.split(r'[,;]', author_from_ai)]
                    # For Bulgarian books, prefer Cyrillic name
                    cyrillic_authors = [a for a in authors_list if any('\u0400' <= char <= '\u04FF' for char in a)]
                    if cyrillic_authors:
                        metadata['author'] = cyrillic_authors[0]
                    else:
                        metadata['author'] = authors_list[0]
                    logger.debug(f"Normalized author from '{author_from_ai}' to '{metadata['author']}'")
            
            # If author is missing but we have content, try to extract it
            if not metadata.get('author') and author:
                # Normalize original author too
                if ',' in author or ';' in author:
                    authors_list = [a.strip() for a in re.split(r'[,;]', author)]
                    cyrillic_authors = [a for a in authors_list if any('\u0400' <= char <= '\u04FF' for char in a)]
                    if cyrillic_authors:
                        metadata['author'] = cyrillic_authors[0]
                    else:
                        metadata['author'] = authors_list[0]
                else:
                    metadata['author'] = author
                logger.debug(f"Using normalized original author as fallback: {metadata['author']}")
            
            # Add citations if available
            if citations and 'sources' not in metadata:
                metadata['sources'] = citations
            
            # Add enrichment metadata
            metadata['enrichment_source'] = 'perplexity'
            metadata['enrichment_model'] = self.model
            metadata['enrichment_date'] = datetime.now().isoformat()
            metadata['original_query'] = {
                'title': title, 
                'author': author
            }
            
            # Calculate quality score
            metadata['quality_score'] = self._calculate_quality(metadata)
            
            # Validate metadata
            if not self._validate_metadata(metadata):
                logger.warning("Metadata validation failed")
                return None
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to parse Perplexity response: {e}")
            return None
    
    def _extract_json(self, content: str) -> Optional[Dict]:
        """
        Extract JSON from response (may have markdown wrapping)
        
        Args:
            content: Response content
            
        Returns:
            Parsed JSON dictionary or None
        """
        
        # Clean up common issues
        content = content.strip()
        
        try:
            # Try 1: Direct JSON parse
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        try:
            # Try 2: Find JSON in markdown code block
            json_match = re.search(
                r'```(?:json)?\s*(\{.*?\})\s*```', 
                content, 
                re.DOTALL | re.IGNORECASE
            )
            if json_match:
                return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
        
        try:
            # Try 3: Find any JSON object
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
        
        logger.warning(f"Could not extract JSON from content: {content[:200]}")
        return None
    
    def _calculate_quality(self, metadata: Dict) -> float:
        """
        Calculate quality score based on completeness and confidence
        
        Args:
            metadata: Parsed metadata
            
        Returns:
            Quality score from 0.0 to 1.0
        """
        
        score = 0.0
        
        # Critical fields (0.6 total)
        if metadata.get('title'): 
            score += 0.20
        if metadata.get('author'): 
            score += 0.20
        if metadata.get('description') and len(metadata['description']) > 50: 
            score += 0.20
        
        # Important fields (0.3 total)
        if metadata.get('publisher'): 
            score += 0.10
        if metadata.get('isbn'): 
            score += 0.10
        if metadata.get('cover_url'): 
            score += 0.10
        
        # Nice-to-have fields (0.1 total)
        if metadata.get('year'): 
            score += 0.03
        if metadata.get('pages'): 
            score += 0.03
        if metadata.get('genres') and len(metadata['genres']) > 0: 
            score += 0.04
        
        # AI confidence boost (if provided)
        ai_confidence = metadata.get('confidence', 0.5)
        if ai_confidence > 0.8:
            score *= 1.05  # 5% bonus for high confidence
        
        # Source quality boost
        sources = metadata.get('sources', [])
        if any('chitanka' in s for s in sources):
            score *= 1.05  # 5% bonus for Chitanka source
        
        return min(1.0, score)
    
    def _validate_metadata(self, metadata: Dict) -> bool:
        """
        Validate that metadata meets minimum requirements
        
        Args:
            metadata: Parsed metadata
            
        Returns:
            True if valid, False otherwise
        """
        
        # Must have at least title and author
        if not metadata.get('title'):
            logger.warning("Missing title in metadata")
            return False
        
        if not metadata.get('author'):
            logger.warning("Missing author in metadata")
            return False
        
        # Quality score must be above threshold
        quality = metadata.get('quality_score', 0)
        if quality < 0.4:
            logger.warning(f"Quality score too low: {quality}")
            return False
        
        return True
    
    async def find_cover_image(
        self, 
        title: str, 
        author: str,
        isbn: Optional[str] = None
    ) -> Optional[str]:
        """
        Specific query for finding cover image URL
        
        Args:
            title: Book title
            author: Book author
            isbn: ISBN if available
            
        Returns:
            Direct URL to cover image or None
        """
        
        logger.info(f"🖼️  Searching for cover: {title}")
        
        # Check if book is Bulgarian (has Cyrillic in title)
        has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in title)
        
        if has_cyrillic:
            query = f"""
Намери ДИРЕКТЕН URL към изображение на корицата за БЪЛГАРСКАТА книга:

ЗАГЛАВИЕ: {title}
АВТОР: {author}
"""
        else:
            query = f"""
Find DIRECT URL to cover image for the ENGLISH book:

TITLE: {title}
AUTHOR: {author}
"""
        
        if isbn:
            query += f"ISBN: {isbn}\n"
        
        query += """

ВАЖНО:
- Търся ВИСОКО КАЧЕСТВО изображение на корицата
- URL трябва да сочи ДИРЕКТНО към изображение (.jpg, .png, .webp)
- Предпочитай формат като:
  * https://biblioman.chitanka.info/thumb/covers/.../xxx.1000.jpg
  * https://chitanka.info/thumb/book/xxx.250.jpg
  * https://ciela.com/media/catalog/product/.../xxx.jpg

ИЗТОЧНИЦИ ЗА ПРОВЕРКА (по приоритет):
1. biblioman.chitanka.info
2. chitanka.info  
3. ciela.com
4. helikon.bg
5. publishers websites (Колибри, Изток-Запад, Хермес, Бард)

ОТГОВОРИ САМО С URL или "NOT_FOUND":
https://direkten-url-kam-izobrajenie.jpg

Ако не намериш качествена корица, отговори: NOT_FOUND
"""
        
        try:
            response = await self._search(query)
            
            if not response:
                return None
            
            content = response['choices'][0]['message']['content'].strip()
            
            # Extract URL from response
            url = self._extract_image_url(content)
            
            if url and url != "NOT_FOUND":
                # Verify URL is accessible
                if await self._verify_image_url(url):
                    logger.info(f"✅ Found cover: {url}")
                    return url
                else:
                    logger.warning(f"⚠️  Cover URL not accessible: {url}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding cover: {e}")
            return None
    
    def _extract_image_url(self, text: str) -> Optional[str]:
        """
        Extract image URL from response
        
        Args:
            text: Response text
            
        Returns:
            Image URL or None
        """
        
        # Check for NOT_FOUND
        if "NOT_FOUND" in text.upper():
            return None
        
        # Look for common image URL patterns
        patterns = [
            # Specific Bulgarian sites
            r'https?://biblioman\.chitanka\.info/thumb/covers/[^\s\)]+\.(?:jpg|jpeg|png|webp)',
            r'https?://chitanka\.info/thumb/[^\s\)]+\.(?:jpg|jpeg|png|webp)',
            r'https?://ciela\.com/media/catalog/product/[^\s\)]+\.(?:jpg|jpeg|png|webp)',
            
            # Generic image URLs
            r'https?://[^\s\)]+\.(?:jpg|jpeg|png|gif|webp)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                url = match.group(0)
                # Clean up potential trailing characters
                url = re.sub(r'[,\)\]\'\"]+$', '', url)
                return url
        
        return None
    
    async def _verify_image_url(self, url: str) -> bool:
        """
        Verify that image URL is accessible
        
        Args:
            url: Image URL to verify
            
        Returns:
            True if accessible, False otherwise
        """
        
        try:
            response = await self.client.head(url, timeout=5.0)
            
            if response.status_code == 200:
                # Check content type
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type.lower():
                    return True
            
            # Some servers don't support HEAD, try GET
            response = await self.client.get(
                url, 
                timeout=5.0,
                follow_redirects=True
            )
            return response.status_code == 200
            
        except Exception as e:
            logger.debug(f"Failed to verify image URL: {e}")
            return False
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    def __repr__(self):
        return f"PerplexityEnricher(model={self.model})"

