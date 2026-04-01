"""Database initialization and helpers."""

import logging
import time

from flask_sqlalchemy import SQLAlchemy

logger = logging.getLogger(__name__)

db = SQLAlchemy()


def _import_models():
    """Import all models so SQLAlchemy metadata knows about them."""
    import app.models  # noqa: F401


def init_db(app, max_retries=5, retry_delay=2):
    """Initialize database: create tables with retry logic for Docker startup."""
    _import_models()
    for attempt in range(1, max_retries + 1):
        try:
            with app.app_context():
                db.create_all()
                _run_migrations()
                logger.info("database.initialized", extra={"attempt": attempt})
                return
        except Exception as e:
            if attempt == max_retries:
                logger.error("database.init_failed", extra={"attempt": attempt, "error": str(e)})
                raise
            logger.warning(
                "database.init_retry",
                extra={"attempt": attempt, "max": max_retries, "error": str(e)},
            )
            time.sleep(retry_delay)


def _run_migrations():
    """Apply lightweight column additions for existing tables.

    SQLAlchemy's create_all() only creates new tables, not new columns.
    This adds any missing columns with safe ALTER TABLE ADD IF NOT EXISTS.
    """
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE calendar ADD COLUMN IF NOT EXISTS time_format VARCHAR(2) NOT NULL DEFAULT '24'",
        "ALTER TABLE calendar ADD COLUMN IF NOT EXISTS date_format VARCHAR(2) NOT NULL DEFAULT 'EU'",
        "ALTER TABLE member ADD COLUMN IF NOT EXISTS birthday DATE",
        "ALTER TABLE calendar ADD COLUMN IF NOT EXISTS show_birthdays BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE calendar ADD COLUMN IF NOT EXISTS show_holidays BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE calendar ADD COLUMN IF NOT EXISTS holiday_country VARCHAR(2)",
        "ALTER TABLE calendar ADD COLUMN IF NOT EXISTS show_weather BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE calendar ADD COLUMN IF NOT EXISTS weather_lat DOUBLE PRECISION",
        "ALTER TABLE calendar ADD COLUMN IF NOT EXISTS weather_lon DOUBLE PRECISION",
    ]
    for sql in migrations:
        try:
            db.session.execute(text(sql))
        except Exception as e:
            logger.debug("migration.skip", extra={"sql": sql, "error": str(e)})
    db.session.commit()
