"""
Text utilities for Cyrillic and Unicode text handling.

Provides functions for detecting Cyrillic text and normalizing text
while preserving Cyrillic characters for search and comparison.
"""
import unicodedata
import re
from typing import Optional


def is_cyrillic(text: str) -> bool:
    """
    Check if text contains Cyrillic characters.
    
    Cyrillic Unicode range: U+0400 to U+04FF
    Includes Bulgarian, Russian, Serbian, and other Cyrillic scripts.
    
    Args:
        text: Text to check
        
    Returns:
        True if text contains any Cyrillic characters, False otherwise
    """
    if not text:
        return False
    
    return any('\u0400' <= char <= '\u04FF' for char in text)


def normalize_text(text: str, preserve_cyrillic: bool = True) -> str:
    """
    Normalize text for search/comparison while preserving Cyrillic characters.
    
    This function:
    - Converts to lowercase
    - Preserves Cyrillic characters if preserve_cyrillic=True
    - Normalizes non-Cyrillic characters to ASCII
    - Removes extra whitespace
    
    Args:
        text: Text to normalize
        preserve_cyrillic: If True, preserve Cyrillic characters as-is
        
    Returns:
        Normalized text string
    """
    if not text:
        return ""
    
    normalized = text.lower().strip()
    
    if preserve_cyrillic:
        result = []
        for char in normalized:
            # Cyrillic range: U+0400 to U+04FF
            if '\u0400' <= char <= '\u04FF':
                result.append(char)  # Keep Cyrillic as-is
            elif char.isspace():
                result.append(' ')  # Normalize whitespace
            elif char.isalnum():
                # Normalize non-Cyrillic to ASCII
                try:
                    normalized_char = unicodedata.normalize('NFKD', char)
                    ascii_char = normalized_char.encode('ASCII', 'ignore').decode('ASCII')
                    result.append(ascii_char if ascii_char else char)
                except Exception:
                    result.append(char)  # Fallback: keep original
            else:
                # Remove punctuation and special characters
                pass
        
        normalized = ''.join(result)
    else:
        # Full ASCII normalization
        normalized = unicodedata.normalize('NFKD', normalized)
        normalized = normalized.encode('ASCII', 'ignore').decode('ASCII')
    
    # Normalize whitespace
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def should_use_biblioman(title: Optional[str] = None, author: Optional[str] = None) -> bool:
    """
    Determine if Biblioman provider should be used for a search.
    
    Biblioman is prioritized for Bulgarian/Cyrillic books.
    
    Args:
        title: Book title
        author: Author name
        
    Returns:
        True if Biblioman should be used (Cyrillic detected), False otherwise
    """
    if title and is_cyrillic(title):
        return True
    if author and is_cyrillic(author):
        return True
    return False

