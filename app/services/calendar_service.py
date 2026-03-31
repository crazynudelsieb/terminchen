"""Calendar business logic."""

import logging

from werkzeug.security import generate_password_hash, check_password_hash

from app.database import db
from app.models import Calendar
from app.utils import sanitize_html

logger = logging.getLogger(__name__)


def create_calendar(name, description, timezone,
                    default_view='month', week_start=0, owner_email=None):
    """Create a new calendar and return it."""
    cal = Calendar(
        name=sanitize_html(name),
        description=sanitize_html(description),
        timezone=timezone,
        default_view=default_view,
        week_start=week_start,
        owner_email=owner_email.strip().lower() if owner_email else None,
    )
    db.session.add(cal)
    db.session.commit()
    logger.info("calendar.created", extra={"calendar_id": str(cal.id), "cal_name": cal.name})
    return cal


def get_calendar_by_share_token(share_token):
    """Look up a calendar by its read-only share token."""
    return Calendar.query.filter_by(share_token=share_token).first()


def get_calendar_by_manager_token(manager_token):
    """Look up a calendar by its manager token."""
    return Calendar.query.filter_by(manager_token=manager_token).first()


def get_calendar_by_admin_token(admin_token):
    """Look up a calendar by its admin token."""
    return Calendar.query.filter_by(admin_token=admin_token).first()


def update_calendar_settings(cal, **kwargs):
    """Update calendar settings from a dict of field values."""
    allowed_fields = {
        'name', 'description', 'timezone', 'default_view',
        'week_start', 'embed_allowed', 'time_format',
        'date_format', 'show_birthdays', 'show_holidays', 'holiday_country',
        'show_weather', 'weather_lat', 'weather_lon',
    }
    for key, value in kwargs.items():
        if key in allowed_fields:
            if key in ('name', 'description'):
                value = sanitize_html(value)
            setattr(cal, key, value)

    db.session.commit()
    logger.info("calendar.updated", extra={"calendar_id": str(cal.id)})
    return cal


def set_admin_password(cal, password):
    """Set or update the admin password. Pass None/empty to remove."""
    if password:
        cal.admin_password_hash = generate_password_hash(password)
        logger.info("calendar.password_set", extra={"calendar_id": str(cal.id)})
    else:
        cal.admin_password_hash = None
        logger.info("calendar.password_removed", extra={"calendar_id": str(cal.id)})
    db.session.commit()


def check_admin_password(cal, password):
    """Check if the given password matches the calendar's admin password."""
    if not cal.admin_password_hash:
        return True  # No password set
    return check_password_hash(cal.admin_password_hash, password)


def get_calendars_by_owner_email(email):
    """Return all calendars linked to a given owner email."""
    return Calendar.query.filter_by(
        owner_email=email.strip().lower()
    ).order_by(Calendar.created_at.desc()).all()


def regenerate_all_tokens(cal):
    """Regenerate all access tokens (share, manager, admin) for a calendar.

    Used in case of token compromise.  Returns a dict with the new tokens.
    """
    import secrets as _secrets
    cal.share_token = _secrets.token_urlsafe(12)
    cal.manager_token = _secrets.token_urlsafe(16)
    cal.admin_token = _secrets.token_urlsafe(24)
    db.session.commit()
    logger.info("calendar.tokens_regenerated", extra={"calendar_id": str(cal.id)})
    return {
        'share_token': cal.share_token,
        'manager_token': cal.manager_token,
        'admin_token': cal.admin_token,
    }


def delete_calendar(cal):
    """Delete a calendar and all associated data (cascade)."""
    cal_id = str(cal.id)
    db.session.delete(cal)
    db.session.commit()
    logger.info("calendar.deleted", extra={"calendar_id": cal_id})
