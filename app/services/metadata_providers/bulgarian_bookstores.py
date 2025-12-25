"""
Bulgarian Bookstore Scraper
Извлича информация за книги от български онлайн книжарници като ozone.bg, ciela.com, helikon.bg и др.

Author: MyBibliotheca Team
Created: 2025-12-25
"""

import requests
import re
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class BulgarianBookstoreScraper:
    """Scraper for Bulgarian online bookstores"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def scrape_book_from_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape book information from a Bulgarian bookstore URL
        
        Args:
            url: URL to scrape (e.g., https://www.ozone.bg/product/imadzhika/)
            
        Returns:
            Dictionary with book metadata or None if failed
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            
            logger.info(f"🔍 Scraping book from: {domain}")
            
            # Route to appropriate scraper based on domain
            if 'ozone.bg' in domain:
                return self._scrape_ozone(url)
            elif 'ciela.com' in domain:
                return self._scrape_ciela(url)
            elif 'helikon.bg' in domain:
                return self._scrape_helikon(url)
            elif 'book.store.bg' in domain:
                return self._scrape_bookstore(url)
            elif 'knigomania.bg' in domain:
                return self._scrape_knigomania(url)
            else:
                logger.warning(f"⚠️  Unknown bookstore domain: {domain}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error scraping {url}: {e}", exc_info=True)
            return None
    
    def _scrape_ozone(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape book information from ozone.bg"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title_elem = soup.find('h1', class_='page-title') or soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else None
            
            # Extract all data from product info table (two-column layout)
            # Ozone.bg uses a table with labels in first column and values in second column
            isbn = None
            isbn13 = None
            isbn10 = None
            author = None
            publisher = None
            year = None
            pages = None
            categories = []
            translator = None
            
            # Find all tables and divs that might contain product info
            info_containers = []
            info_containers.extend(soup.find_all('table'))
            info_containers.extend(soup.find_all('div', class_=re.compile(r'product.*info|product.*details', re.I)))
            
            for container in info_containers:
                # Try table rows
                rows = container.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        
                        if 'isbn' in label or 'баркод' in label:
                            isbn = value
                            isbn_clean = re.sub(r'[^\d]', '', isbn)
                            if len(isbn_clean) == 13:
                                isbn13 = isbn_clean
                            elif len(isbn_clean) == 10:
                                isbn10 = isbn_clean
                        elif 'автор' in label:
                            author = value
                        elif 'издателство' in label:
                            publisher = value
                        elif 'година' in label:
                            year_match = re.search(r'\d{4}', value)
                            if year_match:
                                year = year_match.group(0)
                        elif 'страници' in label or 'брой страници' in label:
                            pages_match = re.search(r'\d+', value)
                            if pages_match:
                                pages = int(pages_match.group(0))
                        elif 'категории' in label or 'жанрове' in label:
                            categories = [c.strip() for c in re.split(r'[,;\n]', value) if c.strip()]
                        elif 'преводач' in label:
                            translator = value
                
                # Also try div-based layouts (some sites use divs instead of tables)
                info_items = container.find_all(['div', 'dl', 'li'], class_=re.compile(r'info|detail|spec', re.I))
                for item in info_items:
                    label_elem = item.find(['dt', 'span', 'strong', 'b'], class_=re.compile(r'label|title', re.I))
                    value_elem = item.find(['dd', 'span', 'div'], class_=re.compile(r'value|content', re.I))
                    
                    if label_elem and value_elem:
                        label = label_elem.get_text(strip=True).lower()
                        value = value_elem.get_text(strip=True)
                        
                        if 'isbn' in label or 'баркод' in label:
                            isbn = value
                            isbn_clean = re.sub(r'[^\d]', '', isbn)
                            if len(isbn_clean) == 13:
                                isbn13 = isbn_clean
                            elif len(isbn_clean) == 10:
                                isbn10 = isbn_clean
                        elif 'автор' in label:
                            author = value
                        elif 'издателство' in label:
                            publisher = value
                        elif 'година' in label:
                            year_match = re.search(r'\d{4}', value)
                            if year_match:
                                year = year_match.group(0)
                        elif 'страници' in label or 'брой страници' in label:
                            pages_match = re.search(r'\d+', value)
                            if pages_match:
                                pages = int(pages_match.group(0))
                        elif 'категории' in label or 'жанрове' in label:
                            categories = [c.strip() for c in re.split(r'[,;\n]', value) if c.strip()]
                        elif 'преводач' in label:
                            translator = value
            
            # Also try to find ISBN in meta tags or script tags
            if not isbn:
                meta_isbn = soup.find('meta', {'property': 'product:isbn'}) or \
                           soup.find('meta', {'name': 'isbn'}) or \
                           soup.find('meta', {'property': 'og:isbn'})
                if meta_isbn:
                    isbn = meta_isbn.get('content', '')
                    isbn_clean = re.sub(r'[^\d]', '', isbn)
                    if len(isbn_clean) == 13:
                        isbn13 = isbn_clean
                    elif len(isbn_clean) == 10:
                        isbn10 = isbn_clean
            
            # Extract cover image
            cover_url = None
            # Try multiple selectors for cover image
            cover_selectors = [
                ('img', {'class': re.compile(r'product.*image', re.I)}),
                ('img', {'id': re.compile(r'product.*image', re.I)}),
                ('img', {'data-src': True}),
                ('img', {'src': re.compile(r'media.*catalog.*product', re.I)}),
            ]
            
            for tag, attrs in cover_selectors:
                cover_img = soup.find(tag, attrs)
                if cover_img:
                    cover_url = cover_img.get('src') or cover_img.get('data-src') or cover_img.get('data-lazy-src')
                    if cover_url:
                        # Make URL absolute if relative
                        if cover_url.startswith('//'):
                            cover_url = 'https:' + cover_url
                        elif cover_url.startswith('/'):
                            cover_url = f"https://{urlparse(url).netloc}{cover_url}"
                        break
            
            # Extract description
            description = None
            desc_selectors = [
                ('div', {'class': re.compile(r'description', re.I)}),
                ('div', {'id': re.compile(r'description', re.I)}),
                ('p', {'class': re.compile(r'description', re.I)}),
            ]
            
            for tag, attrs in desc_selectors:
                desc_elem = soup.find(tag, attrs)
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    if description and len(description) > 50:
                        break
            
            # Build result
            result = {
                'title': title,
                'author': author,
                'publisher': publisher,
                'year': year,
                'pages': pages,
                'isbn': isbn,
                'isbn13': isbn13,
                'isbn10': isbn10,
                'categories': categories,
                'translator': translator,
                'cover_url': cover_url,
                'description': description,
                'source': 'ozone.bg',
                'source_url': url
            }
            
            # Remove None values
            result = {k: v for k, v in result.items() if v is not None}
            
            logger.info(f"✅ Scraped from ozone.bg: {title} by {author}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error scraping ozone.bg: {e}", exc_info=True)
            return None
    
    def _scrape_ciela(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape book information from ciela.com"""
        # Similar implementation for ciela.com
        # TODO: Implement if needed
        return None
    
    def _scrape_helikon(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape book information from helikon.bg"""
        # Similar implementation for helikon.bg
        # TODO: Implement if needed
        return None
    
    def _scrape_bookstore(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape book information from book.store.bg"""
        # Similar implementation for book.store.bg
        # TODO: Implement if needed
        return None
    
    def _scrape_knigomania(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape book information from knigomania.bg"""
        # Similar implementation for knigomania.bg
        # TODO: Implement if needed
        return None

