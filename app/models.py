"""SQLAlchemy ORM models for terminchen."""

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID

from app.database import db


def _uuid():
    return uuid.uuid4()


def _utcnow():
    return datetime.now(timezone.utc)


def _generate_share_token():
    return secrets.token_urlsafe(12)  # ~16 chars


def _generate_manager_token():
    return secrets.token_urlsafe(16)  # ~22 chars


def _generate_admin_token():
    return secrets.token_urlsafe(24)  # ~32 chars


# ── Predefined member colors (auto-assigned round-robin) ──
MEMBER_COLORS = [
    '#16a34a', '#2ecc71', '#f59e0b', '#dc2626', '#9b59b6',
    '#1abc9c', '#e67e22', '#3498db', '#e91e63', '#00bcd4',
    '#8bc34a', '#ff5722', '#607d8b', '#795548', '#cddc39',
]


class Calendar(db.Model):
    __tablename__ = 'calendar'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    timezone = db.Column(db.String(64), nullable=False, default='Europe/Berlin')

    # Tokens
    share_token = db.Column(db.String(16), unique=True, nullable=False, default=_generate_share_token)
    manager_token = db.Column(db.String(24), unique=True, nullable=False, default=_generate_manager_token)
    admin_token = db.Column(db.String(32), unique=True, nullable=False, default=_generate_admin_token)
    admin_password_hash = db.Column(db.String(256), nullable=True)
    owner_email = db.Column(db.String(320), nullable=True)  # optional, for link recovery

    # Settings
    default_view = db.Column(db.String(16), nullable=False, default='month')
    week_start = db.Column(db.SmallInteger, nullable=False, default=0)  # 0=Monday
    color_primary = db.Column(db.String(7), nullable=False, default='#16a34a')
    embed_allowed = db.Column(db.Boolean, nullable=False, default=True)
    time_format = db.Column(db.String(2), nullable=False, default='24')  # '24' or '12'
    date_format = db.Column(db.String(2), nullable=False, default='EU')  # 'EU' (dd.mm) or 'US' (mm/dd)
    show_birthdays = db.Column(db.Boolean, nullable=False, default=True)
    show_holidays = db.Column(db.Boolean, nullable=False, default=True)
    holiday_country = db.Column(db.String(2), nullable=True)  # ISO 3166-1 alpha-2; NULL = auto-detect
    show_weather = db.Column(db.Boolean, nullable=False, default=True)
    weather_lat = db.Column(db.Float, nullable=True)   # manual lat/lon override
    weather_lon = db.Column(db.Float, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    members = db.relationship('Member', back_populates='calendar', cascade='all, delete-orphan',
                              order_by='Member.sort_order')
    events = db.relationship('Event', back_populates='calendar', cascade='all, delete-orphan',
                             order_by='Event.start_time')
    tags = db.relationship('EventTag', back_populates='calendar', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Calendar {self.name}>'


class Member(db.Model):
    __tablename__ = 'member'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    calendar_id = db.Column(UUID(as_uuid=True), db.ForeignKey('calendar.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    icon_filename = db.Column(db.String(255), nullable=True)
    color = db.Column(db.String(7), nullable=False, default='#16a34a')
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    birthday = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    calendar = db.relationship('Calendar', back_populates='members')
    rsvps = db.relationship('RSVP', back_populates='member', cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_member_calendar', 'calendar_id'),
    )

    @property
    def initials(self):
        """First letter(s) of name for avatar fallback."""
        parts = self.name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.name[0].upper() if self.name else '?'

    @property
    def avatar_url(self):
        """URL to avatar image — uploaded file, or DiceBear random avatar."""
        if self.icon_filename:
            return f'/uploads/avatars/{self.icon_filename}'
        # DiceBear random avatar seeded by member UUID (deterministic per member)
        return f'https://api.dicebear.com/9.x/fun-emoji/svg?seed={self.id}'

    @property
    def has_custom_avatar(self):
        """True if the member uploaded their own avatar."""
        return bool(self.icon_filename)

    def __repr__(self):
        return f'<Member {self.name} [{self.calendar_id}]>'


# M2M association: event ↔ tag (must be defined before Event class)
event_tag_assignment = db.Table(
    'event_tag_assignment',
    db.Column('event_id', UUID(as_uuid=True), db.ForeignKey('event.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', UUID(as_uuid=True), db.ForeignKey('event_tag.id', ondelete='CASCADE'), primary_key=True),
)


class Event(db.Model):
    __tablename__ = 'event'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    calendar_id = db.Column(UUID(as_uuid=True), db.ForeignKey('calendar.id', ondelete='CASCADE'), nullable=False)
    share_token = db.Column(db.String(16), unique=True, nullable=False, default=_generate_share_token)

    # Content
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)
    all_day = db.Column(db.Boolean, nullable=False, default=False)

    # Links
    location = db.Column(db.String(500), nullable=True)
    location_url = db.Column(db.String(2048), nullable=True)
    event_url = db.Column(db.String(2048), name='whatsapp_url', nullable=True)

    # Tracking
    created_by_member_id = db.Column(UUID(as_uuid=True), db.ForeignKey('member.id', ondelete='SET NULL'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    calendar = db.relationship('Calendar', back_populates='events')
    rsvps = db.relationship('RSVP', back_populates='event', cascade='all, delete-orphan')
    created_by = db.relationship('Member', foreign_keys=[created_by_member_id])
    tags = db.relationship('EventTag', secondary=event_tag_assignment, back_populates='events')

    __table_args__ = (
        Index('idx_event_calendar_start', 'calendar_id', 'start_time'),
    )

    @property
    def rsvp_summary(self):
        """Return dict with RSVP counts: {in: N, maybe: N, out: N}."""
        counts = {'in': 0, 'maybe': 0, 'out': 0}
        for rsvp in self.rsvps:
            if rsvp.status in counts:
                counts[rsvp.status] += 1
        return counts

    def __repr__(self):
        return f'<Event {self.title}>'


class RSVP(db.Model):
    __tablename__ = 'rsvp'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    event_id = db.Column(UUID(as_uuid=True), db.ForeignKey('event.id', ondelete='CASCADE'), nullable=False)
    member_id = db.Column(UUID(as_uuid=True), db.ForeignKey('member.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='in')  # in / maybe / out
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    # Relationships
    event = db.relationship('Event', back_populates='rsvps')
    member = db.relationship('Member', back_populates='rsvps')

    __table_args__ = (
        UniqueConstraint('event_id', 'member_id', name='uq_rsvp_event_member'),
        Index('idx_rsvp_event_member', 'event_id', 'member_id'),
        Index('idx_rsvp_member', 'member_id'),
    )

    def __repr__(self):
        return f'<RSVP {self.member_id} → {self.event_id}: {self.status}>'


class EventTag(db.Model):
    __tablename__ = 'event_tag'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    calendar_id = db.Column(UUID(as_uuid=True), db.ForeignKey('calendar.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), nullable=False, default='#16a34a')

    # Relationships
    calendar = db.relationship('Calendar', back_populates='tags')
    events = db.relationship('Event', secondary=event_tag_assignment, back_populates='tags')

    __table_args__ = (
        UniqueConstraint('calendar_id', 'name', name='uq_tag_calendar_name'),
        Index('idx_tag_calendar', 'calendar_id'),
    )

    def __repr__(self):
        return f'<EventTag {self.name} [{self.calendar_id}]>'


class PushSubscription(db.Model):
    """Web Push notification subscription.

    Stores browser push endpoints per calendar so we can send event reminders.
    """
    __tablename__ = 'push_subscription'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    calendar_id = db.Column(UUID(as_uuid=True), db.ForeignKey('calendar.id', ondelete='CASCADE'), nullable=False)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column(db.String(256), nullable=False)
    auth = db.Column(db.String(128), nullable=False)
    member_id = db.Column(UUID(as_uuid=True), db.ForeignKey('member.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    calendar = db.relationship('Calendar')
    member = db.relationship('Member')

    __table_args__ = (
        UniqueConstraint('endpoint', name='uq_push_endpoint'),
        Index('idx_push_calendar', 'calendar_id'),
    )

    def __repr__(self):
        return f'<PushSubscription {self.calendar_id}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    calendar_id = db.Column(UUID(as_uuid=True), db.ForeignKey('calendar.id', ondelete='CASCADE'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # e.g. event.created, rsvp.changed
    detail = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)

    # Relationships
    calendar = db.relationship('Calendar', backref=db.backref('audit_logs', lazy='dynamic'))

    __table_args__ = (
        Index('idx_audit_calendar_created', 'calendar_id', 'created_at'),
    )

    def __repr__(self):
        return f'<AuditLog {self.action} [{self.calendar_id}]>'
