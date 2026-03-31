"""Audit log service."""

from app.database import db
from app.models import AuditLog


def log_action(calendar, action, detail=None):
    """Record an action in the audit log."""
    entry = AuditLog(
        calendar_id=calendar.id,
        action=action,
        detail=detail[:500] if detail else None,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def get_recent_logs(calendar, limit=20):
    """Return the most recent audit log entries for a calendar."""
    return AuditLog.query.filter_by(
        calendar_id=calendar.id
    ).order_by(AuditLog.created_at.desc()).limit(limit).all()
