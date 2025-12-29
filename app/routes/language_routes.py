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
    
    # Force session save
    try:
        from flask import current_app
        current_app.session_interface.save_session(current_app, session, None)
    except Exception as e:
        logger.warning(f"Could not force save session: {e}")
    
    print(f"🌐 [LANGUAGE] Language set to: {language}")
    print(f"🌐 [LANGUAGE] Session language value: {session.get('language')}")
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
