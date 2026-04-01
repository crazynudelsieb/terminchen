"""WTForms form definitions."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    EmailField,
    PasswordField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, Optional, URL, ValidationError

from zoneinfo import available_timezones, ZoneInfo

# ── Common timezone choices (grouped, sorted) ──
_COMMON_TZ_PREFIXES = ['Europe/', 'America/', 'Asia/', 'Australia/', 'Pacific/', 'Africa/']


def _timezone_choices():
    """Build a sorted list of timezone choices for select fields."""
    all_tz = sorted(available_timezones())
    if not all_tz:
        # Fallback: if zoneinfo has no data (e.g. Windows without tzdata),
        # provide an empty list -- the client-side JS will populate the dropdown
        return [('', '-- Select timezone --')]
    choices = [('', '-- Select timezone --')]
    for prefix in _COMMON_TZ_PREFIXES:
        group = [(tz, tz.replace('_', ' ')) for tz in all_tz if tz.startswith(prefix)]
        choices.extend(group)
    # Add remaining
    covered = set()
    for prefix in _COMMON_TZ_PREFIXES:
        covered.update(tz for tz in all_tz if tz.startswith(prefix))
    remaining = [(tz, tz.replace('_', ' ')) for tz in all_tz if tz not in covered and '/' in tz]
    choices.extend(remaining)
    return choices


TIMEZONE_CHOICES = _timezone_choices()

VIEW_CHOICES = [
    ('month', 'Month'),
    ('week', 'Week'),
    ('agenda', 'Agenda'),
]

WEEK_START_CHOICES = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]

TIME_FORMAT_CHOICES = [
    ('24', '24-hour (14:30)'),
    ('12', '12-hour (2:30 PM)'),
]

DATE_FORMAT_CHOICES = [
    ('EU', 'DD/MM/YYYY (30/03/2026)'),
    ('US', 'MM/DD/YYYY (03/30/2026)'),
]


class CreateCalendarForm(FlaskForm):
    """Form for creating a new calendar."""
    name = StringField('Calendar Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=2000)])
    timezone = SelectField('Timezone', choices=TIMEZONE_CHOICES, validate_choice=False,
                           validators=[DataRequired()])
    owner_email = EmailField('Email Address', validators=[Optional(), Email(), Length(max=320)],
                             description='Receive your calendar links by email (optional)')

    def validate_timezone(self, field):
        """Accept any valid IANA timezone (handles client-side populated dropdown)."""
        try:
            ZoneInfo(field.data)
        except (KeyError, Exception):
            raise ValidationError('Invalid timezone.')


class CalendarSettingsForm(FlaskForm):
    """Form for editing calendar settings."""
    name = StringField('Calendar Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=2000)])
    timezone = SelectField('Timezone', choices=TIMEZONE_CHOICES, validate_choice=False,
                           validators=[DataRequired()])
    default_view = SelectField('Default View', choices=VIEW_CHOICES, validators=[DataRequired()])
    week_start = SelectField('Week Starts On', choices=WEEK_START_CHOICES, validators=[DataRequired()])
    time_format = SelectField('Time Format', choices=TIME_FORMAT_CHOICES, validators=[DataRequired()])
    date_format = SelectField('Date Format', choices=DATE_FORMAT_CHOICES, validators=[DataRequired()])
    embed_allowed = BooleanField('Allow Embedding', default=True)
    show_birthdays = BooleanField('Show member birthdays on calendar', default=True)
    show_holidays = BooleanField('Show public holidays on calendar', default=True)
    holiday_country = SelectField('Holiday Country', validators=[Optional()])
    show_weather = BooleanField('Show weather forecast on calendar', default=True)
    weather_lat = StringField('Latitude', validators=[Optional(), Length(max=20)])
    weather_lon = StringField('Longitude', validators=[Optional(), Length(max=20)])
    admin_password = PasswordField('Admin Password (leave empty to remove)', validators=[Optional(), Length(max=128)])

    def validate_timezone(self, field):
        """Accept any valid IANA timezone (handles client-side populated dropdown)."""
        try:
            ZoneInfo(field.data)
        except (KeyError, Exception):
            raise ValidationError('Invalid timezone.')


class EventForm(FlaskForm):
    """Form for creating/editing an event."""
    title = StringField('Title', validators=[DataRequired(), Length(max=300)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=5000)])
    start_date = StringField('Start Date & Time', validators=[DataRequired()])  # datetime-local input
    end_date = StringField('End Date & Time', validators=[Optional()])
    all_day = BooleanField('All Day Event', default=False)
    location = StringField('Location', validators=[Optional(), Length(max=500)])
    location_url = StringField('Location Link', validators=[Optional(), URL(), Length(max=2048)])
    whatsapp_url = StringField('WhatsApp Group Link', validators=[Optional(), URL(), Length(max=2048)])


class MemberForm(FlaskForm):
    """Form for adding/editing a member."""
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    color = StringField('Color', validators=[Optional(), Length(max=7)])
    birthday = StringField('Birthday', validators=[Optional(), Length(max=10)])


class TagForm(FlaskForm):
    """Form for creating/editing an event tag."""
    name = StringField('Name', validators=[DataRequired(), Length(max=50)])
    color = StringField('Color', default='#16a34a', validators=[Optional(), Length(max=7)])


class MemberIconForm(FlaskForm):
    """Form for uploading a member icon."""
    icon = FileField('Avatar Image', validators=[
        DataRequired(),
        FileAllowed(['jpg', 'jpeg', 'png', 'webp', 'gif'], 'Images only (JPG, PNG, WebP, GIF)'),
    ])


class AdminAuthForm(FlaskForm):
    """Password entry form for password-protected admin access."""
    password = PasswordField('Admin Password', validators=[DataRequired()])


class RecoverForm(FlaskForm):
    """Form for recovering calendar links by email."""
    email = EmailField('Email Address', validators=[DataRequired(), Email(), Length(max=320)])
