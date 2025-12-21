# Cyrillic Encoding Fix - Summary

## Problem
When searching with Cyrillic characters (e.g., "камък"), the application threw `UnicodeEncodeError` because Werkzeug development server requires latin-1 encoding for HTTP headers, but Cyrillic characters cannot be encoded as latin-1.

## Solution
Implemented two layers of protection:

### 1. Safe Redirect Function (`_safe_redirect` in `app/routes/__init__.py`)
- Properly percent-encodes URLs before redirect
- Handles Cyrillic and other Unicode characters in query parameters
- Ensures path segments are properly encoded if they contain non-ASCII

### 2. Response Middleware (`@app.after_request` in `app/__init__.py`)
- Intercepts all responses before sending
- Checks Location header for non-ASCII characters
- Re-encodes Location header if it contains characters that can't be encoded as latin-1
- Falls back gracefully if encoding fails

## Testing
To test the fix:

1. Start the application:
   ```bash
   source venv/bin/activate
   python dev_run.py
   ```

2. Try searching with Cyrillic characters:
   - Go to library page
   - Search for "камък" or any Bulgarian text
   - Should work without UnicodeEncodeError

3. Check logs:
   - No UnicodeEncodeError should appear
   - Search should work normally

## Files Modified
- `app/routes/__init__.py` - Added `_safe_redirect` function
- `app/__init__.py` - Added `@app.after_request` middleware for Location header encoding

## Notes
- The fix works at two levels: prevention (safe redirect) and safety net (middleware)
- Error handler catches any remaining UnicodeEncodeError and redirects to library without query params
- This fix is specific to Werkzeug development server; production servers (Gunicorn) handle encoding differently

