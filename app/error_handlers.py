"""Custom error handlers."""

import logging

from flask import render_template
from app.database import db

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register custom error pages."""

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        logger.error("server.error_500", exc_info=True)
        return render_template('errors/500.html'), 500
