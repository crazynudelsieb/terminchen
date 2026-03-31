"""Member management business logic."""

import logging
import os
import uuid

from PIL import Image
from werkzeug.utils import secure_filename

from app.database import db
from app.models import Member, MEMBER_COLORS
from app.utils import sanitize_html

logger = logging.getLogger(__name__)


def add_member(calendar, name, color=None, birthday=None):
    """Add a member to a calendar. Auto-assigns color if not provided."""
    if not color:
        idx = len(calendar.members) % len(MEMBER_COLORS)
        color = MEMBER_COLORS[idx]

    # Determine sort order (append at end)
    max_order = db.session.query(db.func.max(Member.sort_order)).filter_by(
        calendar_id=calendar.id
    ).scalar() or 0

    member = Member(
        calendar_id=calendar.id,
        name=sanitize_html(name),
        color=color,
        sort_order=max_order + 1,
        birthday=birthday,
    )
    db.session.add(member)
    db.session.commit()
    logger.info("member.added", extra={
        "calendar_id": str(calendar.id), "member_id": str(member.id), "member_name": member.name
    })
    return member


def update_member(member, name=None, color=None, birthday=None):
    """Update a member's name, color, and/or birthday."""
    if name is not None:
        member.name = sanitize_html(name)
    if color is not None:
        member.color = color
    if birthday is not None:
        member.birthday = birthday if birthday else None
    db.session.commit()
    logger.info("member.updated", extra={"member_id": str(member.id)})
    return member


def deactivate_member(member):
    """Soft-delete a member (hide from new events)."""
    member.is_active = False
    db.session.commit()
    logger.info("member.deactivated", extra={"member_id": str(member.id)})


def reactivate_member(member):
    """Re-activate a soft-deleted member."""
    member.is_active = True
    db.session.commit()
    logger.info("member.reactivated", extra={"member_id": str(member.id)})


def get_member_by_id(member_id):
    """Look up a member by UUID."""
    return Member.query.get(member_id)


def get_active_members(calendar):
    """Get all active members of a calendar, ordered by sort_order."""
    return Member.query.filter_by(
        calendar_id=calendar.id, is_active=True
    ).order_by(Member.sort_order).all()


def get_all_members(calendar):
    """Get all members of a calendar (including inactive), ordered by sort_order."""
    return Member.query.filter_by(
        calendar_id=calendar.id
    ).order_by(Member.sort_order).all()


def process_avatar_upload(member, file_storage, upload_dir):
    """Process and save an avatar image for a member.

    Args:
        member: Member model instance
        file_storage: werkzeug FileStorage from the form
        upload_dir: Base upload directory path

    Returns:
        The saved filename
    """
    avatar_dir = os.path.join(upload_dir, 'avatars')
    os.makedirs(avatar_dir, exist_ok=True)

    # Remove old avatar if exists
    if member.icon_filename:
        old_path = os.path.join(avatar_dir, member.icon_filename)
        if os.path.exists(old_path):
            os.remove(old_path)

    # Process with Pillow: resize, crop to square, convert to WebP
    filename = f"{member.id}.webp"
    filepath = os.path.join(avatar_dir, filename)

    img = Image.open(file_storage)
    img = img.convert('RGB')

    # Strip EXIF data by creating a clean copy
    clean_img = Image.new(img.mode, img.size)
    clean_img.putdata(list(img.getdata()))
    img = clean_img

    # Center crop to square
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    # Resize to 200x200
    img = img.resize((200, 200), Image.LANCZOS)

    # Save as WebP
    img.save(filepath, 'WEBP', quality=85)

    # Update member
    member.icon_filename = filename
    db.session.commit()

    logger.info("member.avatar_uploaded", extra={
        "member_id": str(member.id), "filename": filename
    })
    return filename


def _birthday_in_year(birthday, year):
    """Get the birthday date in a given year, handling Feb 29 → Mar 1 fallback."""
    from datetime import date
    try:
        return date(year, birthday.month, birthday.day)
    except ValueError:
        # Feb 29 in non-leap year → March 1
        return date(year, 3, 1)


def get_birthdays_for_date_range(calendar, start_date, end_date):
    """Get birthday entries for active members within a date range.

    Returns:
        dict mapping date strings (YYYY-MM-DD) to list of dicts
        with keys: member_name, member_color, member_id, birthday_date
    """
    from collections import defaultdict
    from datetime import timedelta

    members = get_active_members(calendar)
    birthdays = defaultdict(list)

    current = start_date
    while current < end_date:
        for m in members:
            if not m.birthday:
                continue
            bday_this_year = _birthday_in_year(m.birthday, current.year)
            if bday_this_year == current:
                birthdays[current.strftime('%Y-%m-%d')].append({
                    'member_name': m.name,
                    'member_color': m.color,
                    'member_id': str(m.id),
                    'birthday_date': m.birthday,
                })
        current += timedelta(days=1)

    return dict(birthdays)


def get_upcoming_birthdays(calendar, days_ahead=90):
    """Get upcoming birthdays as a flat list sorted by next occurrence date.

    Returns:
        list of dicts with keys: date_str, date_obj, member_name, member_color, member_id
    """
    from datetime import date, timedelta

    members = get_active_members(calendar)
    today = date.today()
    result = []

    for m in members:
        if not m.birthday:
            continue
        # Find next occurrence of this birthday
        this_year = _birthday_in_year(m.birthday, today.year)
        if this_year < today:
            next_bday = _birthday_in_year(m.birthday, today.year + 1)
        else:
            next_bday = this_year

        if (next_bday - today).days <= days_ahead:
            result.append({
                'date_str': next_bday.strftime('%Y-%m-%d'),
                'date_obj': next_bday,
                'member_name': m.name,
                'member_color': m.color,
                'member_id': str(m.id),
            })

    result.sort(key=lambda x: x['date_obj'])
    return result
