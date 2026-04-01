"""Application configuration loaded from environment variables."""

import os
from datetime import timedelta


class Config:
    """Flask configuration loaded from .env / environment."""

    @staticmethod
    def load_config(app):
        """Load and validate all configuration into the Flask app."""
        # ── Core ──
        app.config['SECRET_KEY'] = Config._require('SECRET_KEY')
        app.config['SQLALCHEMY_DATABASE_URI'] = Config._require('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['BASE_URL'] = Config._require('BASE_URL').rstrip('/')

        # ── Calendar Defaults ──
        app.config['DEFAULT_TIMEZONE'] = os.getenv('DEFAULT_TIMEZONE', 'Europe/Vienna')
        app.config['DEFAULT_VIEW'] = os.getenv('DEFAULT_VIEW', 'month')
        app.config['DEFAULT_WEEK_START'] = int(os.getenv('DEFAULT_WEEK_START', '0'))

        # ── Upload ──
        max_mb = int(os.getenv('MAX_UPLOAD_SIZE_MB', '2'))
        app.config['MAX_CONTENT_LENGTH'] = max_mb * 1024 * 1024
        app.config['UPLOAD_DIR'] = os.getenv('UPLOAD_DIR', os.path.join(app.root_path, 'uploads'))

        # ── Security ──
        secure = os.getenv('SECURE_COOKIES', 'false').lower() == 'true'
        session_hours = int(os.getenv('SESSION_LIFETIME_HOURS', '720'))
        admin_session_hours = int(os.getenv('ADMIN_SESSION_LIFETIME_HOURS', '24'))

        app.config['SESSION_COOKIE_SECURE'] = secure
        app.config['SESSION_COOKIE_HTTPONLY'] = True
        app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=session_hours)
        app.config['ADMIN_SESSION_LIFETIME_HOURS'] = admin_session_hours

        # ── Integration ──
        cors_origins = os.getenv('CORS_ALLOWED_ORIGINS', '')
        app.config['CORS_ALLOWED_ORIGINS'] = [
            o.strip() for o in cors_origins.split(',') if o.strip()
        ]
        embed_origins = os.getenv('EMBED_ALLOWED_ORIGINS', '')
        app.config['EMBED_ALLOWED_ORIGINS'] = [
            o.strip() for o in embed_origins.split(',') if o.strip()
        ]

        # ── Appearance ──
        app.config['APP_NAME'] = os.getenv('APP_NAME', 'terminchen')
        app.config['APP_TAGLINE'] = os.getenv('APP_TAGLINE', 'Shared calendars for your crew')
        app.config['GITHUB_URL'] = os.getenv('GITHUB_URL', '')
        app.config['SEO_DOMAIN'] = os.getenv('SEO_DOMAIN', '')  # e.g. terminchen.com
        app.config['CLOUDFLARE_BEACON_TOKEN'] = os.getenv('CLOUDFLARE_BEACON_TOKEN', '')

        # ── Legal / Impressum (optional — shown when any LEGAL_ var is set) ──
        app.config['LEGAL_NAME'] = os.getenv('LEGAL_NAME', '')
        app.config['LEGAL_ADDRESS'] = os.getenv('LEGAL_ADDRESS', '')    # use \n for line breaks
        app.config['LEGAL_EMAIL'] = os.getenv('LEGAL_EMAIL', '')
        app.config['LEGAL_PHONE'] = os.getenv('LEGAL_PHONE', '')
        app.config['LEGAL_EXTRA'] = os.getenv('LEGAL_EXTRA', '')        # free-form extra text

        # ── Social / Support Links (optional — shown on Impressum) ──
        app.config['SOCIAL_MASTODON'] = os.getenv('SOCIAL_MASTODON', '')
        app.config['SOCIAL_BLUESKY'] = os.getenv('SOCIAL_BLUESKY', '')
        app.config['SOCIAL_X'] = os.getenv('SOCIAL_X', '')
        app.config['SOCIAL_PATREON'] = os.getenv('SOCIAL_PATREON', '')
        app.config['SOCIAL_KOFI'] = os.getenv('SOCIAL_KOFI', '')
        app.config['SOCIAL_BUYMEACOFFEE'] = os.getenv('SOCIAL_BUYMEACOFFEE', '')
        app.config['SOCIAL_GITHUB'] = os.getenv('SOCIAL_GITHUB', '')
        app.config['SOCIAL_WEBSITE'] = os.getenv('SOCIAL_WEBSITE', '')

        # ── Email / SMTP ──
        app.config['SMTP_HOST'] = os.getenv('SMTP_HOST', '')
        app.config['SMTP_PORT'] = int(os.getenv('SMTP_PORT', '587'))
        app.config['SMTP_USER'] = os.getenv('SMTP_USER', '')
        app.config['SMTP_PASSWORD'] = os.getenv('SMTP_PASSWORD', '')
        app.config['SMTP_USE_TLS'] = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
        app.config['SMTP_FROM_EMAIL'] = os.getenv('SMTP_FROM_EMAIL', os.getenv('SMTP_USER', ''))
        app.config['SMTP_FROM_NAME'] = os.getenv('SMTP_FROM_NAME', app.config['APP_NAME'])

        # ── Web Push (VAPID) ──
        app.config['VAPID_PRIVATE_KEY'] = os.getenv('VAPID_PRIVATE_KEY', '')
        app.config['VAPID_PUBLIC_KEY'] = os.getenv('VAPID_PUBLIC_KEY', '')
        app.config['VAPID_CLAIMS_EMAIL'] = os.getenv('VAPID_CLAIMS_EMAIL',
                                                      app.config.get('LEGAL_EMAIL', ''))

        # ── Logging ──
        app.config['LOG_LEVEL'] = os.getenv('LOG_LEVEL', 'INFO').upper()

    @staticmethod
    def _require(key):
        """Get a required environment variable or raise."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Missing required environment variable: {key}")
        return value
