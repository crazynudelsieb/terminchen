"""Security headers middleware."""

import logging

logger = logging.getLogger(__name__)


def init_security_headers(app):
    """Register after_request handler for security headers."""

    # Build the base CSP once at startup (only frame-ancestors varies per request)
    _CSP_BASE = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: blob: https://api.dicebear.com https://cdn.simpleicons.org; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' https://api.open-meteo.com https://cloudflareinsights.com; "
        "worker-src 'self'; "
    )
    _embed_origins = app.config.get('EMBED_ALLOWED_ORIGINS', [])
    if _embed_origins:
        _frame_ancestors = f"frame-ancestors 'self' {' '.join(_embed_origins)}; "
    else:
        _frame_ancestors = "frame-ancestors 'self'; "
    _CSP_FULL = _CSP_BASE + _frame_ancestors + "form-action 'self';"

    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'

        if not _embed_origins:
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = _CSP_FULL

        # HSTS only when behind HTTPS
        if app.config.get('SESSION_COOKIE_SECURE'):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response
