"""Language switching routes."""
from flask import Blueprint, session, redirect, request, url_for
import logging

logger = logging.getLogger(__name__)
language_bp = Blueprint('language', __name__)

@language_bp.route('/set_language/<language>')
def set_language(language):
    """
    Set the user's preferred language.
    
    Args:
        language (str): Language code (e.g., 'en', 'bg')
    
    Returns:
        redirect: Redirects back to referrer or home
    """
    # Supported languages
    supported_languages = ['en', 'bg']
    
    # Validate language
    if language not in supported_languages:
        language = 'en'  # Default to English
    
    # Store in session and mark as modified
    session['language'] = language
    session.permanent = True  # Make session persistent
    session.modified = True  # Explicitly mark session as modified
    
    # Force Flask-Babel to use the new locale immediately
    try:
        from flask import current_app
        from flask_babel import force_locale, refresh
        
        # Force locale for current request
        with current_app.app_context():
            force_locale(language)
            refresh()
        
        print(f"🌐 [LANGUAGE] Language set to: {language}")
        print(f"🌐 [LANGUAGE] Session language value: {session.get('language')}")
        print(f"🌐 [LANGUAGE] Forced Babel locale to: {language}")
    except Exception as e:
        print(f"🌐 [LANGUAGE] Error setting locale: {e}")
        import traceback
        traceback.print_exc()
        logger.warning(f"Could not force locale: {e}")
    
    logger.info(f"Language set to: {language}, session ID: {session.get('_id', 'unknown')}")
    
    # Redirect back to referrer or library
    referrer = request.referrer
    if referrer and referrer.startswith(request.host_url):
        # Only redirect to referrer if it's from the same host (security)
        return redirect(referrer)
    else:
        # Try to redirect to library if available, otherwise home
        try:
            return redirect(url_for('main.library'))
        except Exception as e:
            logger.warning(f"Could not redirect to library: {e}")
            return redirect('/')
