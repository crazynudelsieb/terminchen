"""iCal feed generation service."""

import logging

import icalendar

from app.services.event_service import get_events_for_calendar

logger = logging.getLogger(__name__)


def generate_ical_feed(calendar):
    """Generate an iCalendar (.ics) feed for a calendar.

    Args:
        calendar: Calendar model instance

    Returns:
        bytes: The .ics file content
    """
    cal = icalendar.Calendar()
    cal.add('prodid', '-//terminchen//EN')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', calendar.name)
    cal.add('x-wr-timezone', calendar.timezone)

    events = get_events_for_calendar(calendar)

    for event in events:
        vevent = icalendar.Event()
        vevent.add('uid', f'{event.id}@zngai-cal')
        vevent.add('summary', event.title)

        if event.all_day:
            # All-day events use DATE type (no time component)
            vevent.add('dtstart', event.start_time.date())
            if event.end_time:
                vevent.add('dtend', event.end_time.date())
        else:
            vevent.add('dtstart', event.start_time)
            if event.end_time:
                vevent.add('dtend', event.end_time)

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
        for member in members:
            if not member.birthday:
                continue
            vevent = icalendar.Event()
            vevent.add('uid', f'birthday-{member.id}@zngai-cal')
            vevent.add('summary', f'\U0001f382 {member.name}\'s birthday')
            vevent.add('dtstart', member.birthday)
            vevent.add('rrule', {'freq': 'yearly'})
            vevent.add('transp', 'TRANSPARENT')
            vevent.add('dtstamp', member.created_at)
            cal.add_component(vevent)

    # Holiday VEVENTs (next 365 days, no RRULE — holidays shift yearly)
    if calendar.show_holidays:
        from datetime import date, timedelta
        from app.services.holiday_service import get_holidays_for_date_range
        today = date.today()
        end = today + timedelta(days=365)
        holidays_by_date = get_holidays_for_date_range(calendar, today, end)
        for date_key, hols in holidays_by_date.items():
            for hol in hols:
                vevent = icalendar.Event()
                vevent.add('uid', f'holiday-{date_key}-{hol["name"]}@zngai-cal')
                vevent.add('summary', f'\U0001f3db {hol["name"]}')
                vevent.add('dtstart', date.fromisoformat(date_key))
                vevent.add('transp', 'TRANSPARENT')
                vevent.add('dtstamp', today)
                cal.add_component(vevent)

    logger.info("feed.generated", extra={
        "calendar_id": str(calendar.id), "event_count": len(events)
    })
    return cal.to_ical()
