"""Language switching routes."""
from flask import Blueprint, session, redirect, request, url_for

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
    
    # Store in session
    session['language'] = language
    session.permanent = True  # Make session persistent
    
    # Redirect back to referrer or home
    referrer = request.referrer
    if referrer:
        return redirect(referrer)
    else:
        return redirect(url_for('home.index') if hasattr(request, 'url_rule') and request.url_rule else '/')
