"""Custom error handlers."""

import logging

from flask import render_template
from app.database import db

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Register custom error pages."""

    @app.errorhandler(400)
    def bad_request(e):
        return render_template('errors/error.html', code=400,
                               message='Bad request. Please check your input and try again.'), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/error.html', code=403,
                               message="You don't have permission to access this page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/error.html', code=404,
                               message="This page doesn't exist. Check the URL or go back home."), 404

    @app.errorhandler(413)
    def payload_too_large(e):
        return render_template('errors/error.html', code=413,
                               message='The uploaded file is too large. Please choose a smaller file.'), 413

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        logger.error("server.error_500", exc_info=True)
        return render_template('errors/error.html', code=500,
                               message='Something went wrong. Please try again later.'), 500
