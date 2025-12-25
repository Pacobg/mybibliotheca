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
            
            # Extract title - try multiple selectors
            title = None
            title_selectors = [
                ('h1', {'class': 'page-title'}),
                ('h1', {}),
                ('h1', {'class': re.compile(r'title', re.I)}),
                ('div', {'class': re.compile(r'product.*title', re.I)}),
            ]
            for tag, attrs in title_selectors:
                title_elem = soup.find(tag, attrs)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title:
                        break
            
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
            info_containers.extend(soup.find_all('div', class_=re.compile(r'product.*info|product.*details|data|spec', re.I)))
            info_containers.extend(soup.find_all('dl'))  # Definition lists
            
            # Also search in the entire body if no containers found
            if not info_containers:
                info_containers = [soup]
            
            for container in info_containers:
                # Try table rows (most common format)
                rows = container.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        
                        if ('isbn' in label or 'баркод' in label) and not isbn:
                            isbn = value
                            isbn_clean = re.sub(r'[^\d]', '', isbn)
                            if len(isbn_clean) == 13:
                                isbn13 = isbn_clean
                            elif len(isbn_clean) == 10:
                                isbn10 = isbn_clean
                        elif 'автор' in label and not author:
                            author = value
                        elif 'издателство' in label and not publisher:
                            publisher = value
                        elif 'година' in label and not year:
                            year_match = re.search(r'\d{4}', value)
                            if year_match:
                                year = year_match.group(0)
                        elif ('страници' in label or 'брой страници' in label) and not pages:
                            pages_match = re.search(r'\d+', value)
                            if pages_match:
                                pages = int(pages_match.group(0))
                        elif ('категории' in label or 'жанрове' in label) and not categories:
                            categories = [c.strip() for c in re.split(r'[,;\n]', value) if c.strip()]
                        elif 'преводач' in label and not translator:
                            translator = value
                
                # Try definition lists (dl/dt/dd format)
                dl_items = container.find_all('dl')
                for dl in dl_items:
                    dts = dl.find_all('dt')
                    dds = dl.find_all('dd')
                    for dt, dd in zip(dts, dds):
                        label = dt.get_text(strip=True).lower()
                        value = dd.get_text(strip=True)
                        
                        if ('isbn' in label or 'баркод' in label) and not isbn:
                            isbn = value
                            isbn_clean = re.sub(r'[^\d]', '', isbn)
                            if len(isbn_clean) == 13:
                                isbn13 = isbn_clean
                            elif len(isbn_clean) == 10:
                                isbn10 = isbn_clean
                        elif 'автор' in label and not author:
                            author = value
                        elif 'издателство' in label and not publisher:
                            publisher = value
                        elif 'година' in label and not year:
                            year_match = re.search(r'\d{4}', value)
                            if year_match:
                                year = year_match.group(0)
                        elif ('страници' in label or 'брой страници' in label) and not pages:
                            pages_match = re.search(r'\d+', value)
                            if pages_match:
                                pages = int(pages_match.group(0))
                        elif ('категории' in label or 'жанрове' in label) and not categories:
                            categories = [c.strip() for c in re.split(r'[,;\n]', value) if c.strip()]
                        elif 'преводач' in label and not translator:
                            translator = value
                
                # Try div-based layouts (some sites use divs with labels and values)
                info_divs = container.find_all(['div', 'li'], class_=re.compile(r'info|detail|spec|attribute', re.I))
                for item in info_divs:
                    # Look for label/strong/bold text followed by value
                    label_elem = item.find(['dt', 'span', 'strong', 'b', 'label'], class_=re.compile(r'label|title|name', re.I))
                    if not label_elem:
                        # Try to find any strong/bold element that might be a label
                        label_elem = item.find(['strong', 'b'])
                    
                    if label_elem:
                        label = label_elem.get_text(strip=True).lower()
                        # Find value - could be in next sibling or in same element
                        value_elem = label_elem.find_next_sibling(['dd', 'span', 'div'])
                        if not value_elem:
                            # Value might be in parent's text after label
                            parent_text = item.get_text(strip=True)
                            if label in parent_text.lower():
                                # Extract text after label
                                value = parent_text.split(label, 1)[-1].strip(' :')
                            else:
                                continue
                        else:
                            value = value_elem.get_text(strip=True)
                        
                        if ('isbn' in label or 'баркод' in label) and not isbn:
                            isbn = value
                            isbn_clean = re.sub(r'[^\d]', '', isbn)
                            if len(isbn_clean) == 13:
                                isbn13 = isbn_clean
                            elif len(isbn_clean) == 10:
                                isbn10 = isbn_clean
                        elif 'автор' in label and not author:
                            author = value
                        elif 'издателство' in label and not publisher:
                            publisher = value
                        elif 'година' in label and not year:
                            year_match = re.search(r'\d{4}', value)
                            if year_match:
                                year = year_match.group(0)
                        elif ('страници' in label or 'брой страници' in label) and not pages:
                            pages_match = re.search(r'\d+', value)
                            if pages_match:
                                pages = int(pages_match.group(0))
                        elif ('категории' in label or 'жанрове' in label) and not categories:
                            categories = [c.strip() for c in re.split(r'[,;\n]', value) if c.strip()]
                        elif 'преводач' in label and not translator:
                            translator = value
                
                # Also try to find text patterns directly in the page
                page_text = container.get_text()
                
                # Look for ISBN pattern
                if not isbn:
                    isbn_patterns = [
                        r'ISBN[:\s]*(\d{13}|\d{10})',
                        r'Баркод[:\s]*(\d{13}|\d{10})',
                        r'(\d{13})',  # 13-digit number
                    ]
                    for pattern in isbn_patterns:
                        match = re.search(pattern, page_text, re.I)
                        if match:
                            isbn_clean = re.sub(r'[^\d]', '', match.group(1) if match.lastindex else match.group(0))
                            if len(isbn_clean) == 13:
                                isbn13 = isbn_clean
                                isbn = isbn_clean
                                break
                            elif len(isbn_clean) == 10:
                                isbn10 = isbn_clean
                                isbn = isbn_clean
                                break
            
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

