"""Production WSGI entry point for Gunicorn."""

from app import create_app

application = create_app()
