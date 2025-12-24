"""
OpenAI/Ollama-based metadata enrichment provider
Uses AI settings from the application configuration (OpenAI or Ollama)

Note: Unlike Perplexity, this provider does NOT have web search capabilities.
It can generate descriptions and parse metadata, but cannot search for covers or 
real-time information from the internet.
"""

import json
import logging
import re
from typing import Dict, Optional, Any
import httpx
from flask import current_app

logger = logging.getLogger(__name__)


class OpenAIEnricher:
    """
    Metadata enrichment using OpenAI or Ollama (from app settings)
    
    Limitations:
    - No web search (cannot find covers or real-time information)
    - Can only generate descriptions based on title/author
    - Cannot fetch ISBNs or publishers from internet
    """
    
    def __init__(self, config: Optional[Dict[str, str]] = None):
        """
        Initialize OpenAI/Ollama enricher
        
        Args:
            config: Optional config dict. If None, loads from app settings
        """
        if config is None:
            # Load from app settings
            try:
                from app.admin import load_ai_config
                config = load_ai_config()
            except Exception as e:
                logger.error(f"Failed to load AI config: {e}")
                config = {}
        
        self.config = config
        self.provider = config.get('AI_PROVIDER', 'openai').lower()
        self.timeout = int(config.get('AI_TIMEOUT', '30'))
        self.max_tokens = int(config.get('AI_MAX_TOKENS', '2000'))
        self.temperature = float(config.get('AI_TEMPERATURE', '0.1'))
        
        logger.info(f"✅ OpenAIEnricher initialized with provider: {self.provider}")
    
    async def fetch_metadata(
        self,
        title: str,
        author: Optional[str] = None,
        isbn: Optional[str] = None,
        publisher: Optional[str] = None,
        existing_data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch metadata for a book using OpenAI/Ollama
        
        Note: This does NOT perform web search. It generates descriptions
        based on the provided information.
        
        Args:
            title: Book title
            author: Book author (optional)
            isbn: ISBN (optional)
            publisher: Publisher (optional)
            existing_data: Existing book data (optional)
            
        Returns:
            Dictionary with metadata or None
        """
        try:
            # Check if book is Bulgarian (has Cyrillic in title)
            has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in title)
            
            # Build query
            query = self._build_metadata_query(title, author, isbn, publisher, has_cyrillic)
            
            # Call AI
            response = await self._call_ai(query)
            
            if not response:
                return None
            
            # Parse response
            metadata = self._parse_response(response, has_cyrillic)
            
            if not metadata:
                return None
            
            # Calculate quality score
            quality = self._calculate_quality_score(metadata)
            metadata['quality_score'] = quality
            
            logger.info(f"✅ Found metadata for: {title} (quality: {quality:.2f})")
            return metadata
            
        except Exception as e:
            logger.error(f"Error fetching metadata: {e}", exc_info=True)
            return None
    
    def _build_metadata_query(
        self,
        title: str,
        author: Optional[str],
        isbn: Optional[str],
        publisher: Optional[str],
        has_cyrillic: bool
    ) -> str:
        """Build query for AI"""
        
        if has_cyrillic:
            # Bulgarian book query
            query = f"""На базата на следната информация за книга, генерирай JSON с метаданни:

ЗАГЛАВИЕ: {title}
"""
            if author:
                query += f"АВТОР: {author}\n"
            if isbn:
                query += f"ISBN: {isbn}\n"
            if publisher:
                query += f"ИЗДАТЕЛСТВО: {publisher}\n"
            
            query += """
ВАЖНО: Това е БЪЛГАРСКА книга. Генерирай информация на български!

ТЪРСЯ СЛЕДНАТА ИНФОРМАЦИЯ:

1. **Точно заглавие** на български
2. **Автор** - ЕДИН основен автор на български
3. **Описание** - 3-4 изречения на български за какво е книгата (базирано на знанията ти за книгата)
4. **Жанр/Категории** (2-4 категории)

ОТГОВОРИ САМО С ВАЛИДЕН JSON ОБЕКТ:

{
    "title": "Заглавие",
    "author": "Автор",
    "description": "Описание на български...",
    "genres": ["Жанр1", "Жанр2"],
    "confidence": 0.8
}

ВАЖНО: Ако не знаеш книгата, върни null за описанието!
"""
        else:
            # English book query
            query = f"""Based on the following book information, generate JSON metadata:

TITLE: {title}
"""
            if author:
                query += f"AUTHOR: {author}\n"
            if isbn:
                query += f"ISBN: {isbn}\n"
            if publisher:
                query += f"PUBLISHER: {publisher}\n"
            
            query += """
IMPORTANT: This is an ENGLISH book. Generate information in English!

I NEED THE FOLLOWING INFORMATION:

1. **Exact title** in English
2. **Author** - ONE main author in English
3. **Description** - 3-4 sentences in English about what the book is about (based on your knowledge)
4. **Genres/Categories** (2-4 categories)

RESPOND ONLY WITH A VALID JSON OBJECT:

{
    "title": "Title",
    "author": "Author",
    "description": "Description in English...",
    "genres": ["Genre1", "Genre2"],
    "confidence": 0.8
}

IMPORTANT: If you don't know the book, return null for description!
"""
        
        return query
    
    async def _call_ai(self, query: str) -> Optional[str]:
        """Call OpenAI or Ollama API"""
        try:
            if self.provider == 'openai':
                return await self._call_openai(query)
            elif self.provider == 'ollama':
                return await self._call_ollama(query)
            else:
                logger.error(f"Unknown provider: {self.provider}")
                return None
        except Exception as e:
            logger.error(f"Error calling AI: {e}", exc_info=True)
            return None
    
    async def _call_openai(self, query: str) -> Optional[str]:
        """Call OpenAI API"""
        try:
            api_key = self.config.get('OPENAI_API_KEY')
            if not api_key:
                logger.error("OpenAI API key not configured")
                return None
            
            base_url = self.config.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
            model = self.config.get('OPENAI_MODEL', 'gpt-4o')
            
            url = f"{base_url}/chat/completions"
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': model,
                'messages': [
                    {
                        'role': 'user',
                        'content': query
                    }
                ],
                'max_tokens': self.max_tokens,
                'temperature': self.temperature,
                'response_format': {'type': 'json_object'}
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                
                if 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0]['message']['content']
                
                return None
                
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return None
    
    async def _call_ollama(self, query: str) -> Optional[str]:
        """Call Ollama API"""
        try:
            base_url = self.config.get('OLLAMA_BASE_URL', 'http://localhost:11434')
            model = self.config.get('OLLAMA_MODEL', 'llama3.2-vision:11b')
            
            # Remove /v1 suffix if present
            if base_url.endswith('/v1'):
                base_url = base_url[:-3]
            
            url = f"{base_url}/api/chat"
            
            payload = {
                'model': model,
                'messages': [
                    {
                        'role': 'user',
                        'content': query
                    }
                ],
                'stream': False,
                'options': {
                    'temperature': self.temperature,
                    'num_predict': self.max_tokens
                },
                'format': 'json'
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()
                
                if 'message' in result and 'content' in result['message']:
                    return result['message']['content']
                
                return None
                
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return None
    
    def _parse_response(self, response_text: str, has_cyrillic: bool) -> Optional[Dict[str, Any]]:
        """Parse AI response"""
        try:
            # Try to extract JSON
            text = response_text.strip()
            
            # Remove markdown code blocks
            if '```json' in text:
                start = text.find('```json') + 7
                end = text.find('```', start)
                if end > start:
                    text = text[start:end].strip()
            elif '```' in text:
                start = text.find('```') + 3
                end = text.find('```', start)
                if end > start:
                    text = text[start:end].strip()
            
            # Parse JSON
            data = json.loads(text)
            
            # Normalize author
            if data.get('author'):
                author = data['author']
                if ',' in author or ';' in author:
                    authors_list = [a.strip() for a in re.split(r'[,;]', author)]
                    if has_cyrillic:
                        cyrillic_authors = [a for a in authors_list if any('\u0400' <= char <= '\u04FF' for char in a)]
                        if cyrillic_authors:
                            data['author'] = cyrillic_authors[0]
                        else:
                            data['author'] = authors_list[0]
                    else:
                        english_authors = [a for a in authors_list if not any('\u0400' <= char <= '\u04FF' for char in a)]
                        if english_authors:
                            data['author'] = english_authors[0]
                        else:
                            data['author'] = authors_list[0]
            
            return data
            
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            logger.debug(f"Response text: {response_text}")
            return None
    
    def _calculate_quality_score(self, metadata: Dict[str, Any]) -> float:
        """Calculate quality score"""
        score = 0.0
        
        if metadata.get('title'):
            score += 0.2
        if metadata.get('author'):
            score += 0.2
        if metadata.get('description'):
            score += 0.4
        if metadata.get('genres'):
            score += 0.2
        
        return min(score, 1.0)
    
    async def find_cover_image(
        self,
        title: str,
        author: str,
        isbn: Optional[str] = None
    ) -> Optional[str]:
        """
        Find cover image URL
        
        NOTE: OpenAI/Ollama cannot search the web for covers.
        This method always returns None.
        """
        logger.warning("⚠️ OpenAI/Ollama provider cannot search for covers (no web search capability)")
        return None

