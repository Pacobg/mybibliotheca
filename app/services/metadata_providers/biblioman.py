"""
Biblioman metadata provider for Bulgarian books.

Integrates with Biblioman database (MariaDB) to provide metadata for Bulgarian books.
Biblioman has 23,000+ Bulgarian book records with ISBN coverage of ~60%.
"""
import os
import logging
import mysql.connector
from typing import Optional, List, Dict, Any
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class BibliomanProvider:
    """Metadata provider for Biblioman database."""
    
    def __init__(self):
        """Initialize Biblioman provider with database connection settings."""
        self.config = {
            'host': os.getenv('BIBLIOMAN_HOST', 'localhost'),
            'port': int(os.getenv('BIBLIOMAN_PORT', '3307')),
            'user': os.getenv('BIBLIOMAN_USER', 'root'),
            'password': os.getenv('BIBLIOMAN_PASSWORD', ''),
            'database': os.getenv('BIBLIOMAN_DATABASE', 'biblioman'),
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'autocommit': True
        }
        self.db = None
        self._enabled = os.getenv('BIBLIOMAN_ENABLED', 'false').lower() == 'true'
    
    def is_enabled(self) -> bool:
        """Check if Biblioman provider is enabled."""
        return self._enabled
    
    def connect(self):
        """Establish database connection."""
        if not self._enabled:
            logger.debug("Biblioman provider is not enabled")
            return False
        
        try:
            if not self.db or not self.db.is_connected():
                logger.debug(f"Connecting to Biblioman database at {self.config['host']}:{self.config['port']}")
                self.db = mysql.connector.connect(**self.config)
                logger.debug("Biblioman database connection established")
            return True
        except mysql.connector.Error as e:
            logger.warning(f"Biblioman database connection failed: {e}")
            logger.debug(f"Connection config: host={self.config['host']}, port={self.config['port']}, user={self.config['user']}, database={self.config['database']}")
            self.db = None
            return False
        except Exception as e:
            logger.warning(f"Failed to connect to Biblioman database: {e}")
            self.db = None
            return False
    
    def close(self):
        """Close database connection."""
        if self.db and self.db.is_connected():
            self.db.close()
            self.db = None
    
    def search_by_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        """Search for book by ISBN (cleaned ISBN-10 or ISBN-13)."""
        if not self.connect():
            return None
        
        try:
            cursor = self.db.cursor(dictionary=True)
            # Clean ISBN: remove dashes and spaces
            clean_isbn = isbn.replace('-', '').replace(' ', '').strip()
            
            # Try both isbn and isbn_clean fields
            sql = """
                SELECT * FROM book 
                WHERE isbn_clean = %s OR isbn = %s 
                LIMIT 1
            """
            cursor.execute(sql, (clean_isbn, clean_isbn))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                logger.debug(f"Biblioman found book by ISBN: {clean_isbn}")
                return self._format_metadata(result)
            return None
        except Exception as e:
            logger.error(f"Biblioman ISBN search error: {e}")
            return None
    
    def search_by_title(self, title: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for books by title (case-insensitive LIKE query)."""
        if not self.connect():
            return []
        
        try:
            cursor = self.db.cursor(dictionary=True)
            sql = """
                SELECT * FROM book 
                WHERE title LIKE %s 
                ORDER BY publishing_year DESC 
                LIMIT %s
            """
            cursor.execute(sql, (f"%{title}%", limit))
            results = cursor.fetchall()
            cursor.close()
            
            formatted = [self._format_metadata(r) for r in results]
            logger.debug(f"Biblioman found {len(formatted)} books by title: {title}")
            return formatted
        except Exception as e:
            logger.error(f"Biblioman title search error: {e}")
            return []
    
    def search_by_author(self, author: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for books by author name."""
        if not self.connect():
            return []
        
        try:
            cursor = self.db.cursor(dictionary=True)
            sql = """
                SELECT * FROM book 
                WHERE author LIKE %s 
                ORDER BY publishing_year DESC 
                LIMIT %s
            """
            cursor.execute(sql, (f"%{author}%", limit))
            results = cursor.fetchall()
            cursor.close()
            
            formatted = [self._format_metadata(r) for r in results]
            logger.debug(f"Biblioman found {len(formatted)} books by author: {author}")
            return formatted
        except Exception as e:
            logger.error(f"Biblioman author search error: {e}")
            return []
    
    def search_by_title_and_author(self, title: str, author: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for books by both title and author."""
        if not self.connect():
            return []
        
        try:
            cursor = self.db.cursor(dictionary=True)
            sql = """
                SELECT * FROM book 
                WHERE title LIKE %s AND author LIKE %s
                ORDER BY publishing_year DESC 
                LIMIT %s
            """
            cursor.execute(sql, (f"%{title}%", f"%{author}%", limit))
            results = cursor.fetchall()
            cursor.close()
            
            formatted = [self._format_metadata(r) for r in results]
            logger.debug(f"Biblioman found {len(formatted)} books by title+author")
            return formatted
        except Exception as e:
            logger.error(f"Biblioman title+author search error: {e}")
            return []
    
    def find_best_match(self, title: str, author: Optional[str] = None, 
                       threshold: float = 0.7) -> Optional[Dict[str, Any]]:
        """
        Find best matching book using fuzzy matching.
        
        Uses SequenceMatcher to calculate similarity scores between search terms
        and database records. Returns the best match if score >= threshold.
        """
        if not self.connect():
            return None
        
        # First try exact title+author match
        if author:
            results = self.search_by_title_and_author(title, author, limit=20)
        else:
            results = self.search_by_title(title, limit=20)
        
        if not results:
            return None
        
        best_match = None
        best_score = 0.0
        
        title_lower = title.lower().strip()
        
        for book in results:
            # Calculate title similarity
            book_title = book.get('title', '') or ''
            title_sim = SequenceMatcher(
                None,
                title_lower,
                book_title.lower()
            ).ratio()
            
            # Calculate author similarity if author provided
            author_sim = 0.0
            if author:
                book_author = book.get('authors', '') or ''
                if isinstance(book_author, list):
                    book_author = ', '.join(book_author)
                if book_author:
                    author_sim = SequenceMatcher(
                        None,
                        author.lower(),
                        book_author.lower()
                    ).ratio()
            
            # Combined score (title weighted 60%, author 40% if provided)
            if author:
                score = title_sim * 0.6 + author_sim * 0.4
            else:
                score = title_sim
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = book
                # Store match score in result
                book['_match_score'] = score
        
        if best_match:
            logger.debug(f"Biblioman best match found: score={best_score:.2f}, title={best_match.get('title')}")
        
        return best_match
    
    def search_metadata(self, title: Optional[str] = None, 
                       author: Optional[str] = None,
                       isbn: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Search for book metadata in Biblioman.
        
        Priority: ISBN > Title+Author > Title only > Author only
        """
        if not self._enabled:
            return None
        
        # Try ISBN first (most accurate)
        if isbn:
            result = self.search_by_isbn(isbn)
            if result:
                return result
        
        # Try title + author
        if title and author:
            result = self.find_best_match(title, author, threshold=0.7)
            if result:
                return result
        
        # Fallback to title only
        if title:
            results = self.search_by_title(title, limit=1)
            if results:
                return results[0]
        
        # Last resort: author only
        if author:
            results = self.search_by_author(author, limit=1)
            if results:
                return results[0]
        
        return None
    
    def _format_metadata(self, book: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format Biblioman data to MyBibliotheca metadata format.
        
        Maps Biblioman database fields to the standard metadata format used
        by Google Books and OpenLibrary providers.
        """
        # Extract ISBNs
        isbn_raw = book.get('isbn') or book.get('isbn_clean') or ''
        isbn_clean = isbn_raw.replace('-', '').replace(' ', '').strip()
        isbn10 = None
        isbn13 = None
        
        if len(isbn_clean) == 10:
            isbn10 = isbn_clean
        elif len(isbn_clean) == 13:
            isbn13 = isbn_clean
        elif isbn_clean:
            # Try to determine format
            if len(isbn_clean) >= 10:
                isbn10 = isbn_clean[:10]
            if len(isbn_clean) >= 13:
                isbn13 = isbn_clean[:13]
        
        # Extract authors (stored as TEXT in Biblioman)
        authors_str = book.get('author', '') or ''
        authors_list = [a.strip() for a in authors_str.split(',') if a.strip()] if authors_str else []
        
        # Format publication date
        pub_year = book.get('publishing_year')
        published_date = str(pub_year) if pub_year else None
        
        # Build Chitanka URL and cover URL if chitanka_id exists
        chitanka_id = book.get('chitanka_id')
        chitanka_url = None
        cover_url = book.get('cover')  # Try direct cover field first
        
        if chitanka_id:
            chitanka_url = f"https://chitanka.info/text/{chitanka_id}"
            # Generate Chitanka cover URL if not already provided
            # Format: https://biblioman.chitanka.info/thumb/covers/{digits}/{chitanka_id}-{hash}.1000.jpg/{filename}
            # Example: https://biblioman.chitanka.info/thumb/covers/6/5/1/6/16516-61e2e079eca99.1000.jpg/...
            if not cover_url:
                # Try to get cover filename from database
                cover_filename = book.get('cover')  # This might be just the filename like "16516-61e2e079eca99.jpg"
                if cover_filename and isinstance(cover_filename, str):
                    # Extract hash from filename (format: {chitanka_id}-{hash}.jpg)
                    if '-' in cover_filename and '.' in cover_filename:
                        # Format: https://biblioman.chitanka.info/thumb/covers/{reversed_digits}/{filename}
                        # For chitanka_id=16516, digits are [6,5,1,6] reversed = [6,1,5,6]
                        chitanka_str = str(chitanka_id)
                        if len(chitanka_str) >= 4:
                            # Take last 4 digits and reverse them
                            digits = list(chitanka_str[-4:])
                            digits.reverse()
                            digits_path = '/'.join(digits)
                            # Use the filename from database, but ensure .1000.jpg extension
                            base_filename = cover_filename.replace('.jpg', '').replace('.jpeg', '')
                            cover_url = f"https://biblioman.chitanka.info/thumb/covers/{digits_path}/{base_filename}.1000.jpg"
                        else:
                            # Fallback: use simple format
                            cover_url = f"https://biblioman.chitanka.info/books/{chitanka_id}/cover"
                    else:
                        # Fallback: use simple format
                        cover_url = f"https://biblioman.chitanka.info/books/{chitanka_id}/cover"
                else:
                    # Fallback: use simple format
                    cover_url = f"https://biblioman.chitanka.info/books/{chitanka_id}/cover"
        
        # Extract categories/genres from Biblioman
        categories = []
        category_id = book.get('category_id')
        if category_id and self.db:
            try:
                cursor = self.db.cursor(dictionary=True)
                # Query category name from label table (Biblioman uses 'label' table for categories)
                sql = """
                    SELECT name FROM label 
                    WHERE id = %s
                    LIMIT 1
                """
                cursor.execute(sql, (category_id,))
                result = cursor.fetchone()
                cursor.close()
                if result and result.get('name'):
                    categories.append(result['name'])
            except Exception as e:
                logger.debug(f"Could not fetch category for book {book.get('id')}: {e}")
        
        # Also check theme/genre fields directly
        theme = book.get('theme') or book.get('genre')
        if theme:
            # Theme might be comma-separated or single value
            if isinstance(theme, str):
                theme_categories = [t.strip() for t in theme.split(',') if t.strip()]
                categories.extend(theme_categories)
            elif isinstance(theme, list):
                categories.extend([str(t).strip() for t in theme if t])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_categories = []
        for cat in categories:
            cat_lower = cat.lower()
            if cat_lower not in seen:
                seen.add(cat_lower)
                unique_categories.append(cat)
        
        return {
            'title': book.get('title') or '',
            'subtitle': book.get('subtitle'),
            'authors': ', '.join(authors_list) if authors_list else '',
            'authors_list': authors_list,
            'description': book.get('annotation'),
            'publisher': book.get('publisher'),
            'published_date': published_date,
            'published_date_raw': published_date,
            'published_date_specificity': 1 if pub_year else 0,  # Year-only specificity
            'isbn': isbn_clean if isbn_clean else None,
            'isbn10': isbn10,  # Keep for backward compatibility
            'isbn13': isbn13,  # Keep for backward compatibility
            'isbn_10': isbn10,  # Standard format used by merge function
            'isbn_13': isbn13,  # Standard format used by merge function
            'isbn_list': [isbn_clean] if isbn_clean else [],
            'page_count': book.get('page_count'),
            'language': book.get('language', 'bg'),  # Default to Bulgarian
            'cover_url': cover_url,
            'categories': unique_categories if unique_categories else [],  # Add categories/genres
            'source': 'Biblioman',
            'biblioman_id': book.get('id'),
            'chitanka_id': chitanka_id,
            'chitanka_url': chitanka_url,
            'chitanka_cover_url': cover_url,  # Explicit cover URL for Chitanka
            'translator': book.get('translator'),
            'editor': book.get('editor'),
            'content_type': book.get('content_type'),
            'nationality': book.get('nationality'),
        }

