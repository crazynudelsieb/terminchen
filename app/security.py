"""Security headers middleware."""

import logging

logger = logging.getLogger(__name__)


def init_security_headers(app):
    """Register after_request handler for security headers."""

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        # X-Frame-Options: allow embedding if configured
        embed_origins = app.config.get('EMBED_ALLOWED_ORIGINS', [])
        if embed_origins:
            # Use CSP frame-ancestors for finer control
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: blob: https://api.dicebear.com https://cdn.simpleicons.org; "
                "font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self' https://api.open-meteo.com https://cloudflareinsights.com; "
                "worker-src 'self'; "
                f"frame-ancestors 'self' {' '.join(embed_origins)}; "
                "form-action 'self';"
            )
        else:
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: blob: https://api.dicebear.com https://cdn.simpleicons.org; "
                "font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self' https://api.open-meteo.com https://cloudflareinsights.com; "
                "worker-src 'self'; "
                "frame-ancestors 'self'; "
                "form-action 'self';"
            )

        # HSTS only when behind HTTPS
        if app.config.get('SESSION_COOKIE_SECURE'):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response
