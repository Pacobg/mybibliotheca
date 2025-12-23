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
            logger.warning(f"🔍 [BIBLIOMAN][ISBN] Cannot connect to database for ISBN: {isbn}")
            return None
        
        try:
            cursor = self.db.cursor(dictionary=True)
            # Clean ISBN: remove dashes and spaces
            clean_isbn = isbn.replace('-', '').replace(' ', '').strip()
            logger.info(f"🔍 [BIBLIOMAN][ISBN] Searching for ISBN: {isbn} (cleaned: {clean_isbn})")
            
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
                logger.info(f"✅ [BIBLIOMAN][ISBN] Found book by ISBN: {clean_isbn}, book_id: {result.get('id')}, chitanka_id: {result.get('chitanka_id')}, cover: {result.get('cover')}")
                formatted = self._format_metadata(result)
                logger.info(f"📚 [BIBLIOMAN][ISBN] Formatted result: cover_url={formatted.get('cover_url')}, chitanka_cover_url={formatted.get('chitanka_cover_url')}, categories={formatted.get('categories')}, chitanka_id={formatted.get('chitanka_id')}")
                # Use builtins.print to ensure this is always visible
                import builtins
                builtins.print(f"✅ [BIBLIOMAN][ISBN] Returning formatted result for ISBN {clean_isbn}: chitanka_id={formatted.get('chitanka_id')}, cover_url={formatted.get('cover_url')}, categories={formatted.get('categories')}")
                return formatted
            else:
                logger.warning(f"⚠️ [BIBLIOMAN][ISBN] No book found for ISBN: {clean_isbn}")
                import builtins
                builtins.print(f"⚠️ [BIBLIOMAN][ISBN] No book found for ISBN: {clean_isbn}")
                # Try partial match as fallback
                sql_partial = """
                    SELECT * FROM book 
                    WHERE isbn_clean LIKE %s OR isbn LIKE %s 
                    LIMIT 1
                """
                cursor = self.db.cursor(dictionary=True)
                cursor.execute(sql_partial, (f"%{clean_isbn}%", f"%{clean_isbn}%"))
                partial_result = cursor.fetchone()
                cursor.close()
                if partial_result:
                    logger.info(f"✅ [BIBLIOMAN][ISBN] Found book by partial ISBN match: {clean_isbn}, book_id: {partial_result.get('id')}")
                    formatted = self._format_metadata(partial_result)
                    logger.info(f"📚 [BIBLIOMAN][ISBN] Formatted partial result: cover_url={formatted.get('cover_url')}, chitanka_cover_url={formatted.get('chitanka_cover_url')}, categories={formatted.get('categories')}")
                    return formatted
            return None
        except Exception as e:
            logger.error(f"❌ [BIBLIOMAN][ISBN] Search error for ISBN {isbn}: {e}", exc_info=True)
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
        cover_url = None
        
        # Get cover field from database (might be filename or URL)
        cover_field = book.get('cover')
        book_id = book.get('id')
        import builtins
        
        # Extract chitanka_id from cover field if chitanka_id is NULL
        # Cover format: {id}-{hash}.jpg (e.g., "16516-61e2e079eca99.jpg")
        # NOTE: cover_field might contain book_id instead of chitanka_id
        # We should NOT extract chitanka_id from cover_field if we already have chitanka_id
        # Only extract if chitanka_id is missing
        if not chitanka_id and cover_field and isinstance(cover_field, str):
            # Try to extract potential ID from cover filename
            # But be careful - this might be book_id, not chitanka_id
            cover_filename = cover_field.strip()
            if '-' in cover_filename:
                try:
                    potential_id = cover_filename.split('-')[0]
                    if potential_id.isdigit():
                        # Only use this as chitanka_id if we don't have one
                        # This is a fallback, but might not always be correct
                        chitanka_id = int(potential_id)
                        builtins.print(f"🔍 [BIBLIOMAN][FORMAT] Extracted potential chitanka_id={chitanka_id} from cover field: {cover_field} (WARNING: might be book_id)")
                except (ValueError, IndexError):
                    pass
        
        builtins.print(f"🔍 [BIBLIOMAN][FORMAT] Book ID: {book_id}, chitanka_id: {chitanka_id}, cover field: {cover_field}")
        logger.info(f"🔍 [BIBLIOMAN] Book ID: {book_id}, chitanka_id: {chitanka_id}, cover field: {cover_field}")
        
        if chitanka_id:
            chitanka_url = f"https://chitanka.info/text/{chitanka_id}"
            
            # Generate Chitanka cover URL
            # Format: https://biblioman.chitanka.info/thumb/covers/{last_4_digits}/{chitanka_id}-{hash}.1000.jpg
            # Example: https://biblioman.chitanka.info/thumb/covers/6/5/1/6/16516-61e2e079eca99.1000.jpg
            if cover_field and isinstance(cover_field, str):
                # Check if it's already a full URL
                if cover_field.startswith('http://') or cover_field.startswith('https://'):
                    cover_url = cover_field
                    logger.debug(f"Biblioman: Using existing full URL: {cover_url}")
                else:
                    # It's just a filename, generate full URL
                    # Format: {id}-{hash}.jpg -> convert to full URL
                    # IMPORTANT: cover_field might contain book_id instead of chitanka_id
                    # We need to use chitanka_id in the URL, not book_id
                    cover_filename = cover_field.strip()
                    logger.debug(f"Biblioman: Generating URL from filename: {cover_filename}")
                    if '-' in cover_filename and '.' in cover_filename:
                        # Extract hash from filename (format: {id}-{hash}.jpg)
                        # The hash is the part after the first dash
                        parts = cover_filename.split('-', 1)
                        if len(parts) == 2:
                            hash_part = parts[1].replace('.jpg', '').replace('.jpeg', '')
                            # Use chitanka_id (not book_id) to build the filename
                            chitanka_str = str(chitanka_id)
                            if len(chitanka_str) >= 4:
                                # Take last 4 digits and split them individually
                                last_four = chitanka_str[-4:]
                                digits_path = '/'.join(list(last_four))
                                # Build filename using chitanka_id + hash from cover_field
                                base_filename = f"{chitanka_id}-{hash_part}"
                                cover_url = f"https://biblioman.chitanka.info/thumb/covers/{digits_path}/{base_filename}.1000.jpg"
                                logger.debug(f"Biblioman: Generated cover URL using chitanka_id={chitanka_id}: {cover_url}")
                                
                                # If the first part of cover_filename matches book_id (not chitanka_id),
                                # the hash might be wrong. Try alternative: use cover_field as-is if it looks like chitanka_id format
                                first_part = parts[0]
                                if first_part.isdigit() and int(first_part) != chitanka_id:
                                    # cover_field starts with book_id, not chitanka_id
                                    # Try using the original cover_filename format but with chitanka_id path
                                    # This is a fallback - the hash might still work
                                    logger.debug(f"Biblioman: cover_field starts with book_id={first_part}, but chitanka_id={chitanka_id}, using chitanka_id-based URL")
                            else:
                                # Fallback: use simple format
                                cover_url = f"https://biblioman.chitanka.info/books/{chitanka_id}/cover"
                                logger.debug(f"Biblioman: Using fallback cover URL (chitanka_id too short): {cover_url}")
                        else:
                            # Fallback: use simple format
                            cover_url = f"https://biblioman.chitanka.info/books/{chitanka_id}/cover"
                            logger.debug(f"Biblioman: Using fallback cover URL (invalid filename format): {cover_url}")
                    else:
                        # Fallback: use simple format
                        cover_url = f"https://biblioman.chitanka.info/books/{chitanka_id}/cover"
                        logger.debug(f"Biblioman: Using fallback cover URL (invalid filename format): {cover_url}")
            else:
                # No cover field, try to generate from chitanka_id
                cover_url = f"https://biblioman.chitanka.info/books/{chitanka_id}/cover"
                logger.debug(f"Biblioman: No cover field, using fallback: {cover_url}")
        
        # Extract categories/genres from Biblioman
        categories = []
        book_id = book.get('id')
        
        if book_id and self.db:
            try:
                cursor = self.db.cursor(dictionary=True)
                
                # First, check if book table has a direct category field
                try:
                    cursor.execute("SHOW COLUMNS FROM book")
                    book_columns = cursor.fetchall()
                    book_column_names = [col.get('Field') or col.get('field') for col in book_columns]
                    logger.debug(f"Biblioman: book table columns: {book_column_names}")
                    
                    # Check if book has category_id or category field
                    if 'category_id' in book_column_names:
                        # Book has direct category_id field
                        sql = """
                            SELECT bc.name 
                            FROM book b
                            JOIN book_category bc ON b.category_id = bc.id
                            WHERE b.id = %s
                        """
                        cursor.execute(sql, (book_id,))
                        result = cursor.fetchone()
                        if result and result.get('name'):
                            categories.append(result['name'])
                            logger.info(f"✅ [BIBLIOMAN][FORMAT] Found category from book.category_id: {result['name']}")
                    elif 'category' in book_column_names:
                        # Book has direct category field (might be name or ID)
                        sql = "SELECT category FROM book WHERE id = %s"
                        cursor.execute(sql, (book_id,))
                        result = cursor.fetchone()
                        if result and result.get('category'):
                            categories.append(str(result['category']))
                            logger.info(f"✅ [BIBLIOMAN][FORMAT] Found category from book.category: {result['category']}")
                except Exception as book_error:
                    builtins.print(f"⚠️ [BIBLIOMAN][FORMAT] Could not check book table: {book_error}")
                
                # If no direct category, check book_multi_field table (might be for many-to-many relationships)
                if not categories:
                    try:
                        cursor.execute("SHOW COLUMNS FROM book_multi_field")
                        bmf_columns = cursor.fetchall()
                        bmf_column_names = [col.get('Field') or col.get('field') for col in bmf_columns]
                        logger.debug(f"Biblioman: book_multi_field table columns: {bmf_column_names}")
                        
                        # Find book and field columns
                        book_col = None
                        field_col = None
                        value_col = None
                        
                        for col in bmf_column_names:
                            col_lower = col.lower()
                            if 'book' in col_lower and book_col is None:
                                book_col = col
                            if 'field' in col_lower and field_col is None:
                                field_col = col
                            if 'value' in col_lower or 'label' in col_lower or 'category' in col_lower:
                                value_col = col
                        
                        if book_col and field_col:
                            # Try to find categories in book_multi_field
                            sql = f"""
                                SELECT {value_col or field_col} as category_value
                                FROM book_multi_field
                                WHERE {book_col} = %s 
                                AND ({field_col} LIKE '%category%' OR {field_col} LIKE '%label%' OR {field_col} LIKE '%genre%')
                            """
                            cursor.execute(sql, (book_id,))
                            results = cursor.fetchall()
                            for result in results:
                                cat_value = result.get('category_value') or result.get(list(result.keys())[0])
                                if cat_value:
                                    # Try to get name from book_category if it's an ID
                                    try:
                                        sql2 = "SELECT name FROM book_category WHERE id = %s"
                                        cursor.execute(sql2, (cat_value,))
                                        cat_result = cursor.fetchone()
                                        if cat_result and cat_result.get('name'):
                                            categories.append(cat_result['name'])
                                        else:
                                            categories.append(str(cat_value))
                                    except:
                                        categories.append(str(cat_value))
                            
                            if categories:
                                logger.info(f"✅ [BIBLIOMAN][FORMAT] Found {len(categories)} categories from book_multi_field: {categories}")
                        else:
                            builtins.print(f"⚠️ [BIBLIOMAN][FORMAT] book_multi_field missing expected columns. Columns: {bmf_column_names}")
                    except Exception as bmf_error:
                        builtins.print(f"⚠️ [BIBLIOMAN][FORMAT] Could not check book_multi_field table: {bmf_error}")
                
                cursor.close()
                    
            except Exception as e:
                builtins.print(f"❌ [BIBLIOMAN][FORMAT] Error checking book and book_multi_field tables: {e}")
                logger.debug(f"Biblioman: Error checking book and book_multi_field tables: {e}")
                # Fallback: try category_id field
                try:
                    category_id = book.get('category_id')
                    if category_id:
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
                            logger.debug(f"Biblioman: Found category from category_id: {result['name']}")
                except Exception as e2:
                    logger.debug(f"Biblioman: Could not fetch category from category_id for book {book.get('id')}: {e2}")
        
        # Also check theme/genre fields directly
        theme = book.get('theme') or book.get('genre')
        if theme:
            # Theme might be comma-separated or single value
            if isinstance(theme, str):
                theme_categories = [t.strip() for t in theme.split(',') if t.strip()]
                categories.extend(theme_categories)
                logger.debug(f"Biblioman: Added {len(theme_categories)} categories from theme/genre field")
            elif isinstance(theme, list):
                categories.extend([str(t).strip() for t in theme if t])
                logger.debug(f"Biblioman: Added {len(theme)} categories from theme/genre list")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_categories = []
        for cat in categories:
            cat_lower = cat.lower()
            if cat_lower not in seen:
                seen.add(cat_lower)
                unique_categories.append(cat)
        
        logger.info(f"📚 [BIBLIOMAN] Final categories for book {book.get('id')}: {unique_categories}")
        logger.info(f"🖼️ [BIBLIOMAN] Final cover_url for book {book.get('id')}: {cover_url}")
        
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

