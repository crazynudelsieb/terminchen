"""Shared utility functions."""

import html
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

import nh3


def generate_token(nbytes=12):
    """Generate a URL-safe token. 12 bytes → ~16 chars."""
    return secrets.token_urlsafe(nbytes)


def local_to_utc(naive_dt, tz_name):
    """Convert a naive local datetime to a UTC-aware datetime.

    Args:
        naive_dt: datetime without tzinfo (as entered in a form)
        tz_name: IANA timezone string, e.g. 'Europe/Berlin'

    Returns:
        datetime with tzinfo=UTC
    """
    local_tz = ZoneInfo(tz_name)
    local_dt = naive_dt.replace(tzinfo=local_tz)
    return local_dt.astimezone(ZoneInfo('UTC'))


def utc_to_local(utc_dt, tz_name):
    """Convert a UTC-aware datetime to a local-aware datetime.

    Args:
        utc_dt: datetime with tzinfo (stored as UTC in DB)
        tz_name: IANA timezone string, e.g. 'Europe/Berlin'

    Returns:
        datetime in the target timezone
    """
    if utc_dt is None:
        return None
    return utc_dt.astimezone(ZoneInfo(tz_name))


def sanitize_html(text):
    """Strip all HTML tags from user input. Allow no tags."""
    if text is None:
        return None
    cleaned = nh3.clean(text, tags=set()).strip()
    # Store plain text (not HTML entities) so templates render characters like '&' naturally.
    return html.unescape(cleaned)


def format_datetime_local(dt, tz_name, fmt='%Y-%m-%d %H:%M', time_format='24', date_format='EU'):
    """Format a UTC datetime for display in a given timezone."""
    if dt is None:
        return ''
    local_dt = utc_to_local(dt, tz_name)
    if fmt == '%Y-%m-%d %H:%M':
        date_part = local_dt.strftime('%d.%m.%Y') if date_format != 'US' else local_dt.strftime('%m/%d/%Y')
        time_part = local_dt.strftime('%I:%M %p').lstrip('0') if time_format == '12' else local_dt.strftime('%H:%M')
        return f'{date_part} {time_part}'
    return local_dt.strftime(fmt)


def format_date_local(dt, tz_name, fmt='%a, %b %d, %Y', date_format='EU'):
    """Format a UTC datetime as a date string in a given timezone.

    date_format:
        'EU' → "Mon, 30.03.2026"
        'US' → "Mon, 03/30/2026"
    """
    if dt is None:
        return ''
    local_dt = utc_to_local(dt, tz_name)
    if fmt == '%a, %b %d, %Y':
        # Apply configurable date format
        if date_format == 'US':
            return local_dt.strftime('%a, %m/%d/%Y')
        else:  # EU default
            return local_dt.strftime('%a, %d.%m.%Y')
    return local_dt.strftime(fmt)


def format_plain_date(d, date_format='EU'):
    """Format a date object (not datetime) for display.

    date_format:
        'EU' → "Mon, 30.03.2026"
        'US' → "Mon, 03/30/2026"
    """
    if d is None:
        return ''
    if isinstance(d, str):
        from datetime import date as date_cls
        d = date_cls.fromisoformat(d)
    if date_format == 'US':
        return d.strftime('%a, %m/%d/%Y')
    return d.strftime('%a, %d.%m.%Y')


def format_time_local(dt, tz_name, fmt='%H:%M', time_format='24'):
    """Format a UTC datetime as a time string in a given timezone."""
    if dt is None:
        return ''
    local_dt = utc_to_local(dt, tz_name)
    if time_format == '12':
        return local_dt.strftime('%I:%M %p').lstrip('0')
    return local_dt.strftime(fmt)
