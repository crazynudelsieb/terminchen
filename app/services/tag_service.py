"""Event tag business logic."""

import logging

from app.database import db
from app.models import EventTag
from app.utils import sanitize_html

logger = logging.getLogger(__name__)


def get_tags_for_calendar(calendar):
    """Return all tags for a calendar, ordered by name."""
    return EventTag.query.filter_by(calendar_id=calendar.id).order_by(EventTag.name).all()


def get_tag_by_id(tag_id, calendar):
    """Return a tag by ID, scoped to the calendar."""
    return EventTag.query.filter_by(id=tag_id, calendar_id=calendar.id).first()


def create_tag(calendar, name, color='#16a34a'):
    """Create a new tag for a calendar."""
    name = sanitize_html(name.strip())
    tag = EventTag(calendar_id=calendar.id, name=name, color=color)
    db.session.add(tag)
    db.session.commit()
    logger.info("tag.created", extra={"tag_id": str(tag.id), "calendar_id": str(calendar.id), "tag_name": name})
    return tag


def update_tag(tag, name=None, color=None):
    """Update a tag's name and/or color."""
    if name is not None:
        tag.name = sanitize_html(name.strip())
    if color is not None:
        tag.color = color
    db.session.commit()
    logger.info("tag.updated", extra={"tag_id": str(tag.id), "tag_name": tag.name})
    return tag


def delete_tag(tag):
    """Delete a tag (cascades to assignments)."""
    tag_id = str(tag.id)
    db.session.delete(tag)
    db.session.commit()
    logger.info("tag.deleted", extra={"tag_id": tag_id})


def set_event_tags(event, tag_ids, calendar):
    """Replace all tags on an event with the given tag IDs."""
    tags = EventTag.query.filter(
        EventTag.id.in_(tag_ids),
        EventTag.calendar_id == calendar.id,
    ).all()
    event.tags = tags
    db.session.commit()
