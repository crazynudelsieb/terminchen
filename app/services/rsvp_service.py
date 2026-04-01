"""RSVP business logic."""

import logging

from app.database import db
from app.models import RSVP, Member

logger = logging.getLogger(__name__)


def set_rsvp(event_id, member_id, status):
    """Set or update an RSVP for a member on an event.

    Args:
        event_id: UUID of the event
        member_id: UUID of the member
        status: 'in', 'maybe', or 'out'

    Returns:
        RSVP instance (created or updated)
    """
    if status not in ('in', 'maybe', 'out'):
        raise ValueError(f"Invalid RSVP status: {status}")

    rsvp = RSVP.query.filter_by(event_id=event_id, member_id=member_id).first()

    if rsvp:
        old_status = rsvp.status
        rsvp.status = status
        logger.info("rsvp.updated", extra={
            "event_id": str(event_id), "member_id": str(member_id),
            "old_status": old_status, "new_status": status,
        })
    else:
        rsvp = RSVP(event_id=event_id, member_id=member_id, status=status)
        db.session.add(rsvp)
        logger.info("rsvp.created", extra={
            "event_id": str(event_id), "member_id": str(member_id), "status": status,
        })

    db.session.commit()
    return rsvp


def bulk_set_rsvp(event, members, status):
    """Set all active members to the given RSVP status for an event.

    Uses a single transaction for efficiency instead of N individual commits.
    Returns the number of RSVPs created/updated.
    """
    if status not in ('in', 'maybe', 'out'):
        raise ValueError(f"Invalid RSVP status: {status}")

    count = 0
    for member in members:
        rsvp = RSVP.query.filter_by(event_id=event.id, member_id=member.id).first()
        if rsvp:
            rsvp.status = status
        else:
            db.session.add(RSVP(event_id=event.id, member_id=member.id, status=status))
        count += 1

    db.session.commit()
    logger.info("rsvp.bulk_set", extra={
        "event_id": str(event.id), "status": status, "count": count,
    })
    return count


def remove_rsvp(event_id, member_id):
    """Remove an RSVP entirely (reset to no response)."""
    rsvp = RSVP.query.filter_by(event_id=event_id, member_id=member_id).first()
    if rsvp:
        db.session.delete(rsvp)
        db.session.commit()
        logger.info("rsvp.removed", extra={
            "event_id": str(event_id), "member_id": str(member_id),
        })


def get_rsvps_for_event(event):
    """Get all RSVPs for an event, grouped by status.

    Returns:
        dict: {
            'in': [Member, ...],
            'maybe': [Member, ...],
            'out': [Member, ...],
            'no_response': [Member, ...],
        }
    """
    # Get all active members of the calendar
    all_members = Member.query.filter_by(
        calendar_id=event.calendar_id, is_active=True
    ).order_by(Member.name.asc(), Member.sort_order.asc()).all()

    # Build RSVP lookup
    rsvps = {r.member_id: r.status for r in event.rsvps}

    result = {'in': [], 'maybe': [], 'out': [], 'no_response': []}
    for member in all_members:
        status = rsvps.get(member.id)
        if status in result:
            result[status].append(member)
        else:
            result['no_response'].append(member)

    return result


def get_member_rsvp(event_id, member_id):
    """Get a single member's RSVP status for an event. Returns status string or None."""
    rsvp = RSVP.query.filter_by(event_id=event_id, member_id=member_id).first()
    return rsvp.status if rsvp else None
