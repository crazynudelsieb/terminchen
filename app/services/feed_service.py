"""iCal feed generation service."""

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import icalendar

from app.services.event_service import get_events_for_calendar

logger = logging.getLogger(__name__)


def _utcnow():
    """Current UTC datetime (for DTSTAMP)."""
    return datetime.now(timezone.utc)


def _make_vtimezone(tz_name):
    """Build a VTIMEZONE component from an IANA timezone name.

    Uses a simple STANDARD/DAYLIGHT pair for the current year.
    Falls back gracefully — returns None if timezone has no transitions.
    """
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    year = now.year

    vtimezone = icalendar.Timezone()
    vtimezone.add('tzid', tz_name)

    # Probe for UTC offset on Jan 1 (winter) and Jul 1 (summer)
    jan = datetime(year, 1, 15, 12, tzinfo=tz)
    jul = datetime(year, 7, 15, 12, tzinfo=tz)
    off_jan = jan.utcoffset()
    off_jul = jul.utcoffset()

    if off_jan == off_jul:
        # No DST — single STANDARD component
        std = icalendar.TimezoneStandard()
        std.add('dtstart', datetime(year, 1, 1, 0, 0, 0))
        std.add('tzoffsetfrom', off_jan)
        std.add('tzoffsetto', off_jan)
        std.add('tzname', jan.strftime('%Z'))
        vtimezone.add_component(std)
    else:
        # DST observed — add both STANDARD and DAYLIGHT
        std = icalendar.TimezoneStandard()
        std.add('dtstart', datetime(year, 1, 1, 0, 0, 0))
        std.add('tzoffsetfrom', off_jul)  # coming from summer
        std.add('tzoffsetto', off_jan)
        std.add('tzname', jan.strftime('%Z'))
        vtimezone.add_component(std)

        dlt = icalendar.TimezoneDaylight()
        dlt.add('dtstart', datetime(year, 7, 1, 0, 0, 0))
        dlt.add('tzoffsetfrom', off_jan)  # coming from winter
        dlt.add('tzoffsetto', off_jul)
        dlt.add('tzname', jul.strftime('%Z'))
        vtimezone.add_component(dlt)

    return vtimezone


def _localize_dt(utc_dt, tz_name):
    """Convert a UTC-aware datetime to the calendar's local timezone."""
    return utc_dt.astimezone(ZoneInfo(tz_name))


def generate_ical_feed(calendar):
    """Generate an iCalendar (.ics) feed for a calendar.

    Args:
        calendar: Calendar model instance

    Returns:
        bytes: The .ics file content
    """
    tz_name = calendar.timezone

    cal = icalendar.Calendar()
    cal.add('prodid', '-//terminchen//EN')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', calendar.name)
    cal.add('x-wr-timezone', tz_name)

    # Add proper VTIMEZONE so clients display correct local times
    vtimezone = _make_vtimezone(tz_name)
    if vtimezone:
        cal.add_component(vtimezone)

    events = get_events_for_calendar(calendar)

    for event in events:
        vevent = icalendar.Event()
        vevent.add('uid', f'{event.id}@terminchen')
        vevent.add('summary', event.title)

        if event.all_day:
            # All-day events use DATE type.
            # Convert UTC to local before extracting .date() so that
            # e.g. 2026-04-02T22:00Z (= 2026-04-03 in Europe/Vienna) → Apr 3.
            local_start = _localize_dt(event.start_time, tz_name)
            start_date = local_start.date()
            vevent.add('dtstart', start_date)
            if event.end_time:
                local_end = _localize_dt(event.end_time, tz_name)
                end_inclusive = local_end.date()
                # RFC 5545: DTEND for DATE values is exclusive → +1 day
                if end_inclusive >= start_date:
                    vevent.add('dtend', end_inclusive + timedelta(days=1))
        else:
            # Timed events: convert to local TZ with TZID so clients
            # display correct times regardless of x-wr-timezone support.
            local_start = _localize_dt(event.start_time, tz_name)
            vevent.add('dtstart', local_start)
            if event.end_time:
                local_end = _localize_dt(event.end_time, tz_name)
                vevent.add('dtend', local_end)

        if event.description:
            vevent.add('description', event.description)
        if event.location:
            vevent.add('location', event.location)
        if event.location_url:
            vevent.add('url', event.location_url)

        vevent.add('dtstamp', event.updated_at or event.created_at)
        cal.add_component(vevent)

    # Birthday VEVENTs (yearly recurring)
    if calendar.show_birthdays:
        from app.services.member_service import get_active_members
        members = get_active_members(calendar)
        now_stamp = _utcnow()
        for member in members:
            if not member.birthday:
                continue
            vevent = icalendar.Event()
            vevent.add('uid', f'birthday-{member.id}@terminchen')
            vevent.add('summary', f'\U0001f382 {member.name}\'s birthday')
            vevent.add('dtstart', member.birthday)
            vevent.add('rrule', {'freq': 'yearly'})
            vevent.add('transp', 'TRANSPARENT')
            vevent.add('dtstamp', member.created_at or now_stamp)
            cal.add_component(vevent)

    # Holiday VEVENTs (next 365 days, no RRULE — holidays shift yearly)
    if calendar.show_holidays:
        from app.services.holiday_service import get_holidays_for_date_range
        today = date.today()
        end = today + timedelta(days=365)
        now_stamp = _utcnow()
        holidays_by_date = get_holidays_for_date_range(calendar, today, end)
        for date_key, hols in holidays_by_date.items():
            for hol in hols:
                vevent = icalendar.Event()
                vevent.add('uid', f'holiday-{date_key}-{hol["name"]}@terminchen')
                vevent.add('summary', f'\U0001f3db {hol["name"]}')
                vevent.add('dtstart', date.fromisoformat(date_key))
                vevent.add('transp', 'TRANSPARENT')
                # RFC 5545: DTSTAMP must be a datetime, not date
                vevent.add('dtstamp', now_stamp)
                cal.add_component(vevent)

    logger.info("feed.generated", extra={
        "calendar_id": str(calendar.id), "event_count": len(events)
    })
    return cal.to_ical()
