"""
Language utilities for GameNetMaster
This file contains utility functions for language detection and handling
"""

from flask import request, session
from translations import get_translation

def get_user_language():
    """
    Gets the user's preferred language from the session
    or falls back to the browser's language preference
    
    Returns:
        str: Language code ('en' or 'fa')
    """
    # Check if the language is stored in the session
    if 'language' in session:
        return session['language']
    
    # If not, try to get it from the Accept-Language header
    if request.accept_languages:
        # Check for Persian (fa) in the accepted languages
        for lang in request.accept_languages.values():
            if lang.startswith('fa'):
                return 'fa'
    
    # Default to English
    return 'en'

def set_user_language(language):
    """
    Sets the user's preferred language in the session
    
    Args:
        language (str): Language code ('en' or 'fa')
    """
    session['language'] = language if language in ['en', 'fa'] else 'en'

def get_direction():
    """
    Gets the text direction based on the current language
    
    Returns:
        str: 'rtl' for Persian, 'ltr' for English
    """
    return 'rtl' if get_user_language() == 'fa' else 'ltr'

def translate(key):
    """
    Translate a key to the user's preferred language
    
    Args:
        key (str): The translation key
        
    Returns:
        str: The translated text
    """
    return get_translation(key, get_user_language())