"""Flask application factory for terminchen."""

import logging
import os

from dotenv import load_dotenv
from flask import Flask

from app.config import Config
from app.database import db, init_db
from app.error_handlers import register_error_handlers
from app.security import init_security_headers
from app.utils import format_datetime_local, format_date_local, format_time_local, utc_to_local


def create_app():
    """Create and configure the Flask application."""
    load_dotenv()

    app = Flask(__name__)
    Config.load_config(app)

    # ── Logging ──
    log_level = getattr(logging, app.config['LOG_LEVEL'], logging.INFO)
    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    app.logger.setLevel(log_level)

    # ── Extensions ──
    db.init_app(app)

    # CSRF protection
    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect(app)

    # CORS for API endpoints
    cors_origins = app.config.get('CORS_ALLOWED_ORIGINS', [])
    if cors_origins:
        from flask_cors import CORS
        CORS(app, resources={r'/api/*': {'origins': cors_origins}})

    # ── Ensure upload directory exists ──
    upload_dir = app.config['UPLOAD_DIR']
    os.makedirs(os.path.join(upload_dir, 'avatars'), exist_ok=True)

    # ── Jinja2 globals & filters ──
    # Build legal context flag (True if any LEGAL_ var is set)
    has_legal = any(app.config.get(k) for k in
                    ('LEGAL_NAME', 'LEGAL_ADDRESS', 'LEGAL_EMAIL', 'LEGAL_PHONE'))

    seo_domain = app.config.get('SEO_DOMAIN', '')
    seo_base_url = f'https://{seo_domain}' if seo_domain else app.config['BASE_URL']

    app.jinja_env.globals.update(
        app_name=app.config['APP_NAME'],
        app_tagline=app.config['APP_TAGLINE'],
        has_legal=has_legal,
        github_url=app.config.get('GITHUB_URL', ''),
        seo_base_url=seo_base_url,
        seo_domain=seo_domain,
        cf_beacon_token=app.config.get('CLOUDFLARE_BEACON_TOKEN', ''),
    )

    @app.template_filter('localtime')
    def _filter_localtime(dt, tz_name, time_format='24', date_format='EU'):
        return format_datetime_local(dt, tz_name, time_format=time_format, date_format=date_format)

    @app.template_filter('localdate')
    def _filter_localdate(dt, tz_name, date_format='EU'):
        return format_date_local(dt, tz_name, date_format=date_format)

    @app.template_filter('localdate_iso')
    def _filter_localdate_iso(dt, tz_name):
        """Return local date as ISO string YYYY-MM-DD (for dict lookups)."""
        from zoneinfo import ZoneInfo
        try:
            local_dt = dt.astimezone(ZoneInfo(tz_name))
            return local_dt.strftime('%Y-%m-%d')
        except Exception:
            return dt.strftime('%Y-%m-%d')

    @app.template_filter('formatdate')
    def _filter_formatdate(d, date_format='EU'):
        from app.utils import format_plain_date
        return format_plain_date(d, date_format=date_format)

    @app.template_filter('localtime_short')
    def _filter_localtime_short(dt, tz_name, time_format='24'):
        return format_time_local(dt, tz_name, time_format=time_format)

    @app.template_filter('localdatetime_input')
    def _filter_localdatetime_input(dt, tz_name):
        """Format for HTML datetime-local input fields."""
        return format_datetime_local(dt, tz_name, fmt='%Y-%m-%dT%H:%M')

    # ── Database ──
    init_db(app)

    # ── Security headers ──
    init_security_headers(app)

    # ── Error handlers ──
    register_error_handlers(app)

    # ── Blueprints ──
    from app.routes import main
    app.register_blueprint(main)

    app.logger.info("app.started", extra={"base_url": app.config['BASE_URL']})
    return app
