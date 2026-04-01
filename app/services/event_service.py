"""Event business logic."""

import calendar as cal_mod
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_
from sqlalchemy.orm import selectinload

from app.database import db
from app.models import Event
from app.utils import sanitize_html, local_to_utc, utc_to_local

logger = logging.getLogger(__name__)

ALLOWED_URL_SCHEMES = re.compile(r'^https?://', re.IGNORECASE)


def _sanitize_url(url):
    """Strip whitespace and reject non-HTTP(S) URLs."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not ALLOWED_URL_SCHEMES.match(url):
        return None
    return url


def create_event(calendar, title, start_time_local, end_time_local=None,
                 all_day=False, description=None, location=None,
                 location_url=None, whatsapp_url=None, created_by_member_id=None):
    """Create a new event on a calendar.

    Args:
        calendar: Calendar model instance
        title: Event title
        start_time_local: Naive datetime in the calendar's timezone
        end_time_local: Optional naive datetime in the calendar's timezone
        all_day: Whether this is an all-day event
        description: Optional event description
        location: Optional location text
        location_url: Optional location URL
        whatsapp_url: Optional WhatsApp group link
        created_by_member_id: Optional UUID of the creating member

    Returns:
        Created Event instance
    """
    # Convert local times to UTC for storage
    if all_day:
        # For all-day events, store start of day UTC (midnight in calendar TZ)
        start_utc = local_to_utc(
            datetime.combine(start_time_local.date(), datetime.min.time()),
            calendar.timezone
        )
        end_utc = None
        if end_time_local:
            end_utc = local_to_utc(
                datetime.combine(end_time_local.date(), datetime.min.time()),
                calendar.timezone
            )
    else:
        start_utc = local_to_utc(start_time_local, calendar.timezone)
        end_utc = local_to_utc(end_time_local, calendar.timezone) if end_time_local else None

    event = Event(
        calendar_id=calendar.id,
        title=sanitize_html(title),
        description=sanitize_html(description),
        start_time=start_utc,
        end_time=end_utc,
        all_day=all_day,
        location=sanitize_html(location),
        location_url=_sanitize_url(location_url),
        whatsapp_url=_sanitize_url(whatsapp_url),
        created_by_member_id=created_by_member_id,
    )
    db.session.add(event)
    db.session.commit()

    logger.info("event.created", extra={
        "calendar_id": str(calendar.id), "event_id": str(event.id), "title": event.title
    })
    return event


def duplicate_event(event, calendar):
    """Duplicate an event with a new share token and no RSVPs.

    Returns the new Event instance.
    """
    new_event = Event(
        calendar_id=calendar.id,
        title=event.title,
        description=event.description,
        start_time=event.start_time,
        end_time=event.end_time,
        all_day=event.all_day,
        location=event.location,
        location_url=event.location_url,
        whatsapp_url=event.whatsapp_url,
    )
    db.session.add(new_event)
    # Copy tag assignments
    new_event.tags = list(event.tags)
    db.session.commit()

    logger.info("event.duplicated", extra={
        "calendar_id": str(calendar.id),
        "source_event_id": str(event.id),
        "new_event_id": str(new_event.id),
    })
    return new_event


def update_event(event, calendar, **kwargs):
    """Update an event. Handles timezone conversion for time fields."""
    time_fields = {'start_time_local', 'end_time_local'}
    simple_fields = {'title', 'description', 'location', 'location_url', 'whatsapp_url', 'all_day'}

    for key, value in kwargs.items():
        if key in simple_fields:
            if key in ('title', 'description', 'location'):
                value = sanitize_html(value)
            elif key in ('location_url', 'whatsapp_url'):
                value = _sanitize_url(value)
            setattr(event, key, value)

    # Handle time updates
    all_day = kwargs.get('all_day', event.all_day)
    start_local = kwargs.get('start_time_local')
    end_local = kwargs.get('end_time_local')

    if start_local is not None:
        if all_day:
            event.start_time = local_to_utc(
                datetime.combine(start_local.date(), datetime.min.time()),
                calendar.timezone
            )
        else:
            event.start_time = local_to_utc(start_local, calendar.timezone)

    if end_local is not None:
        if all_day:
            event.end_time = local_to_utc(
                datetime.combine(end_local.date(), datetime.min.time()),
                calendar.timezone
            )
        else:
            event.end_time = local_to_utc(end_local, calendar.timezone)
    elif 'end_time_local' in kwargs and end_local is None:
        event.end_time = None

    db.session.commit()
    logger.info("event.updated", extra={"event_id": str(event.id)})
    return event


def delete_event(event):
    """Delete an event (cascades to RSVPs)."""
    event_id = str(event.id)
    db.session.delete(event)
    db.session.commit()
    logger.info("event.deleted", extra={"event_id": event_id})


def get_event_by_id(event_id):
    """Look up an event by UUID."""
    return Event.query.get(event_id)


def get_event_by_share_token(share_token):
    """Look up an event by its shareable token."""
    return Event.query.filter_by(share_token=share_token).first()


def get_events_for_calendar(calendar, start=None, end=None, limit=None):
    """Get events for a calendar, optionally filtered by date range.

    Args:
        calendar: Calendar model instance
        start: Optional UTC datetime — events starting on or after this
        end: Optional UTC datetime — events starting before this
        limit: Optional max number of events

    Returns:
        List of Event instances ordered by start_time
    """
    query = Event.query.filter_by(calendar_id=calendar.id).options(
        selectinload(Event.rsvps),
        selectinload(Event.tags),
    )

    if start:
        query = query.filter(Event.start_time >= start)
    if end:
        query = query.filter(Event.start_time < end)

    query = query.order_by(Event.start_time)

    if limit:
        query = query.limit(limit)

    return query.all()


def get_upcoming_events(calendar, limit=20):
    """Get upcoming events from now, ordered by start_time."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return Event.query.filter(
        Event.calendar_id == calendar.id,
        Event.start_time >= now
    ).options(
        selectinload(Event.rsvps),
        selectinload(Event.tags),
    ).order_by(Event.start_time).limit(limit).all()


def _query_and_group_events(calendar, window_start, window_end):
    """Shared: query events overlapping a date window and group by local date.

    Args:
        calendar: Calendar model instance
        window_start: Naive datetime (local TZ) — start of window (inclusive)
        window_end: Naive datetime (local TZ) — end of window (exclusive)

    Returns:
        dict mapping date strings (YYYY-MM-DD) to list of Event instances
    """
    start_utc = local_to_utc(window_start, calendar.timezone)
    end_utc = local_to_utc(window_end, calendar.timezone)

    # Include events that overlap the visible window.
    # Timed events use start_time in-range; all-day events may begin earlier
    # but still overlap if their end_time reaches into the window.
    events = Event.query.filter(
        Event.calendar_id == calendar.id,
        Event.start_time < end_utc,
        or_(
            and_(Event.all_day.is_(False), Event.start_time >= start_utc),
            and_(Event.all_day.is_(True), Event.end_time.is_(None), Event.start_time >= start_utc),
            and_(Event.all_day.is_(True), Event.end_time.is_not(None), Event.end_time >= start_utc),
        ),
    ).options(
        selectinload(Event.rsvps),
        selectinload(Event.tags),
    ).order_by(Event.start_time).all()

    # Group by local date; expand multi-day all-day events across each day
    window_start_date = window_start.date()
    window_end_exclusive = window_end.date()
    grouped = defaultdict(list)
    for event in events:
        local_start = utc_to_local(event.start_time, calendar.timezone)

        if event.all_day and event.end_time:
            local_end = utc_to_local(event.end_time, calendar.timezone)
            current_date = max(local_start.date(), window_start_date)
            end_date = min(local_end.date(), window_end_exclusive - timedelta(days=1))
            while current_date <= end_date:
                grouped[current_date.strftime('%Y-%m-%d')].append(event)
                current_date += timedelta(days=1)
            continue

        date_key = local_start.strftime('%Y-%m-%d')
        grouped[date_key].append(event)

    return dict(grouped)


def get_events_for_month(calendar, year, month):
    """Get events for a specific month and group by local date.

    Returns:
        dict mapping date strings (YYYY-MM-DD) to list of Event instances
    """
    first_day = datetime(year, month, 1)
    if month == 12:
        next_month_start = datetime(year + 1, 1, 1)
    else:
        next_month_start = datetime(year, month + 1, 1)

    return _query_and_group_events(calendar, first_day, next_month_start)


def get_events_for_week(calendar, year, month, day):
    """Get events for a 7-day window starting from a given date, grouped by local date.

    Returns:
        dict mapping date strings (YYYY-MM-DD) to list of Event instances
    """
    week_start = datetime(year, month, day)
    week_end = week_start + timedelta(days=7)

    return _query_and_group_events(calendar, week_start, week_end)
