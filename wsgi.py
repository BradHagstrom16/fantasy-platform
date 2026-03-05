"""
Fantasy Sports Platform - WSGI Entry Point
============================================
Used by PythonAnywhere (and other WSGI servers).
"""
from app import create_app

application = create_app()
