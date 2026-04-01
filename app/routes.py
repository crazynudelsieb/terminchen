"""Main application routes."""

import calendar as cal_mod
import logging
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (
    Blueprint, abort, current_app, flash, jsonify, make_response,
    redirect, render_template, request, session, url_for,
)
from sqlalchemy import text

from app.database import db
from app.forms import (
    AdminAuthForm, CalendarSettingsForm, CreateCalendarForm,
    EventForm, MemberForm, MemberIconForm, RecoverForm, TagForm,
)
from app.services import calendar_service, event_service, member_service, rsvp_service, feed_service
from app.services import tag_service, audit_service, holiday_service, weather_service, email_service
from app.services.upload_service import serve_avatar

logger = logging.getLogger(__name__)

main = Blueprint('main', __name__)


# ── Helpers ──────────────────────────────────────────────


def _parse_uuid(value):
    """Safely parse a string to UUID, or abort 404."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        abort(404)


def _parse_birthday(date_str):
    """Parse a YYYY-MM-DD string into a date object, or None."""
    if not date_str or not date_str.strip():
        return None
    try:
        return datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_float(value):
    """Parse a string to float, or None if empty/invalid."""
    if not value or not value.strip():
        return None
    try:
        return float(value.strip())
    except (ValueError, TypeError):
        return None


def _get_calendar_or_404(share_token):
    """Look up calendar by share token or abort."""
    cal = calendar_service.get_calendar_by_share_token(share_token)
    if not cal:
        abort(404)
    return cal


def _require_manager(share_token, manager_token):
    """Validate manager access: correct share + manager tokens."""
    cal = _get_calendar_or_404(share_token)

    if not secrets.compare_digest(cal.manager_token, manager_token):
        abort(403)

    return cal


def _require_admin(share_token, admin_token):
    """Validate admin access: correct tokens + optional password check."""
    cal = _get_calendar_or_404(share_token)

    # Verify admin token matches this calendar (constant-time comparison)
    if not secrets.compare_digest(cal.admin_token, admin_token):
        abort(403)

    # Check password if set
    if cal.admin_password_hash:
        session_key = f'admin_auth_{admin_token}'
        if not session.get(session_key):
            # Redirect to password entry
            return cal, False  # Not authenticated

    return cal, True  # Authenticated


def _parse_event_datetime(date_str, time_str=None):
    """Parse date + optional time inputs to a naive datetime.

    Accepts:
        - date_str: 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM' (datetime-local fallback)
        - time_str: 'HH:MM' (from separate time input)
    """
    if not date_str:
        return None
    date_str = date_str.strip()
    # If time_str provided, combine with date
    if time_str and time_str.strip():
        t = time_str.strip()
        # Bare hour (e.g. "19") → "19:00"
        if t.isdigit() and len(t) <= 2:
            t = t.zfill(2) + ':00'
        combined = f"{date_str}T{t}"
        try:
            return datetime.strptime(combined, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
    # Fallback: datetime-local format
    try:
        return datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    except ValueError:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return None


def _get_calendar_overlays(cal, start_date, end_date):
    """Fetch birthday, holiday, and weather overlays for a date range.

    Returns:
        (birthdays_by_date, holidays_by_date, weather_by_date) — each a dict
    """
    birthdays_by_date = (
        member_service.get_birthdays_for_date_range(cal, start_date, end_date)
        if cal.show_birthdays else {}
    )
    holidays_by_date = (
        holiday_service.get_holidays_for_date_range(cal, start_date, end_date)
        if cal.show_holidays else {}
    )
    weather_by_date = (
        weather_service.get_weather_for_date_range(cal, start_date, end_date)
        if cal.show_weather else {}
    )
    return birthdays_by_date, holidays_by_date, weather_by_date


def _get_create_event_url(cal):
    """Build the create-event URL if the session has admin or manager tokens."""
    share = cal.share_token
    admin_tok = session.get(f'admin_token_{share}')
    mgr_tok = session.get(f'manager_token_{share}')
    if admin_tok:
        return url_for('main.create_event', share_token=share, admin_token=admin_tok)
    if mgr_tok:
        return url_for('main.manager_create_event', share_token=share, manager_token=mgr_tok)
    return None


# ── Health ───────────────────────────────────────────────


@main.route('/health')
def health():
    """Health check endpoint for Docker/monitoring."""
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify(status='healthy', db='connected'), 200
    except Exception:
        return jsonify(status='unhealthy', db='disconnected'), 503


# ── Landing Page ─────────────────────────────────────────


@main.route('/')
def index():
    """Landing page with create calendar form."""
    form = CreateCalendarForm()
    return render_template('index.html', form=form)


@main.route('/impressum')
def impressum():
    """Impressum / legal notice page (contact details from LEGAL_* env vars)."""
    cfg = current_app.config
    if not any(cfg.get(k) for k in ('LEGAL_NAME', 'LEGAL_ADDRESS', 'LEGAL_EMAIL', 'LEGAL_PHONE')):
        abort(404)
    # Collect social links: list of dicts with label, url, and simpleicons slug
    social_links = []
    _social_map = [
        ('SOCIAL_MASTODON',     'Mastodon',        'mastodon'),
        ('SOCIAL_BLUESKY',      'Bluesky',         'bluesky'),
        ('SOCIAL_X',            'X',               'x'),
        ('SOCIAL_PATREON',      'Patreon',         'patreon'),
        ('SOCIAL_KOFI',         'Ko-fi',           'kofi'),
        ('SOCIAL_BUYMEACOFFEE', 'Buy Me a Coffee', 'buymeacoffee'),
        ('SOCIAL_GITHUB',       'GitHub',          'github'),
        ('SOCIAL_WEBSITE',      'Website',         ''),
    ]
    for key, label, si_slug in _social_map:
        url = cfg.get(key, '')
        if url:
            social_links.append({'label': label, 'url': url, 'icon_slug': si_slug})

    return render_template('impressum.html',
                           legal_name=cfg.get('LEGAL_NAME', ''),
                           legal_address=cfg.get('LEGAL_ADDRESS', ''),
                           legal_email=cfg.get('LEGAL_EMAIL', ''),
                           legal_phone=cfg.get('LEGAL_PHONE', ''),
                           legal_extra=cfg.get('LEGAL_EXTRA', ''),
                           social_links=social_links)


@main.route('/privacy')
def privacy():
    """Privacy policy page (GDPR-required for EU hosting)."""
    cfg = current_app.config
    return render_template('privacy.html',
                           legal_name=cfg.get('LEGAL_NAME', ''),
                           legal_email=cfg.get('LEGAL_EMAIL', ''))


@main.route('/sw.js')
def service_worker():
    """Serve service worker at root scope so it controls all app pages."""
    response = current_app.make_response(
        current_app.send_static_file('sw.js')
    )
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-store'
    return response


@main.route('/robots.txt')
def robots_txt():
    """Serve robots.txt for search engine crawlers."""
    seo_domain = current_app.config.get('SEO_DOMAIN', '')
    base = f'https://{seo_domain}' if seo_domain else current_app.config['BASE_URL']
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /cal/*/admin/',
        'Disallow: /cal/*/manage/',
        'Disallow: /api/',
        '',
        f'Sitemap: {base}/sitemap.xml',
    ]
    resp = make_response('\n'.join(lines))
    resp.headers['Content-Type'] = 'text/plain'
    return resp


@main.route('/sitemap.xml')
def sitemap():
    """XML sitemap for search engines."""
    seo_domain = current_app.config.get('SEO_DOMAIN', '')
    base = f'https://{seo_domain}' if seo_domain else current_app.config['BASE_URL']
    today = date.today().isoformat()

    pages = [
        ('/', '1.0', 'weekly'),
        ('/recover', '0.3', 'yearly'),
        ('/privacy', '0.2', 'yearly'),
    ]
    cfg = current_app.config
    if any(cfg.get(k) for k in ('LEGAL_NAME', 'LEGAL_ADDRESS', 'LEGAL_EMAIL', 'LEGAL_PHONE')):
        pages.append(('/impressum', '0.2', 'yearly'))

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for path, priority, freq in pages:
        xml += f'  <url>\n'
        xml += f'    <loc>{base}{path}</loc>\n'
        xml += f'    <lastmod>{today}</lastmod>\n'
        xml += f'    <changefreq>{freq}</changefreq>\n'
        xml += f'    <priority>{priority}</priority>\n'
        xml += f'  </url>\n'
    xml += '</urlset>'
    resp = make_response(xml)
    resp.headers['Content-Type'] = 'application/xml'
    return resp


@main.route('/create', methods=['POST'])
def create_calendar():
    """Create a new calendar."""
    form = CreateCalendarForm()
    if form.validate_on_submit():
        cal = calendar_service.create_calendar(
            name=form.name.data,
            description=form.description.data,
            timezone=form.timezone.data,
            owner_email=(form.owner_email.data or '').strip() or None,
        )

        # Send calendar links via email if an address was provided
        owner_email = (form.owner_email.data or '').strip()
        if owner_email:
            base = current_app.config['BASE_URL']
            share_url = f"{base}/cal/{cal.share_token}"
            manager_url = f"{base}/cal/{cal.share_token}/manage/{cal.manager_token}"
            admin_url = f"{base}/cal/{cal.share_token}/admin/{cal.admin_token}"
            sent = email_service.send_calendar_links(
                to_email=owner_email,
                calendar_name=cal.name,
                share_url=share_url,
                manager_url=manager_url,
                admin_url=admin_url,
            )
            if sent:
                flash('Calendar created! Links have been sent to your email.', 'success')
            else:
                flash('Calendar created! Bookmark your admin link. (Email could not be sent.)', 'warning')
        else:
            flash('Calendar created! Bookmark your admin link.', 'success')

        return redirect(url_for('main.admin_dashboard',
                                share_token=cal.share_token,
                                admin_token=cal.admin_token))
    # Re-render with errors
    return render_template('index.html', form=form), 400


@main.route('/recover', methods=['GET', 'POST'])
def recover():
    """Recover calendar admin links by email."""
    form = RecoverForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        calendars = calendar_service.get_calendars_by_owner_email(email)
        if calendars:
            base = current_app.config['BASE_URL']
            email_service.send_recovery_email(email, calendars, base)
        # Always show the same message to prevent email enumeration
        flash('If that email is linked to any calendars, you will receive an email shortly.', 'info')
        return redirect(url_for('main.recover'))
    return render_template('recover.html', form=form)


# ── Calendar Views (Read-Only) ───────────────────────────


@main.route('/cal/<share_token>')
def calendar_view(share_token):
    """Default calendar view (respects calendar's default_view setting)."""
    cal = _get_calendar_or_404(share_token)
    return redirect(url_for(f'main.calendar_{cal.default_view}', share_token=share_token))


@main.route('/cal/<share_token>/month')
def calendar_month(share_token):
    """Month view."""
    cal = _get_calendar_or_404(share_token)

    # Determine which month to show (query params or current month in cal TZ)
    now_local = datetime.now(ZoneInfo(cal.timezone))
    year = request.args.get('year', now_local.year, type=int)
    month = request.args.get('month', now_local.month, type=int)

    # Build month grid data
    _, days_in_month = cal_mod.monthrange(year, month)
    first_weekday = cal_mod.weekday(year, month, 1)  # 0=Monday

    events_by_date = event_service.get_events_for_month(cal, year, month)
    events = event_service.get_upcoming_events(cal, limit=100)
    members = member_service.get_active_members(cal)
    selected_member_id = session.get(f'member_{share_token}')

    # Overlay data (birthdays, holidays, weather)
    month_start = date(year, month, 1)
    month_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    birthdays_by_date, holidays_by_date, weather_by_date = _get_calendar_overlays(
        cal, month_start, month_end)

    # Previous / next month for navigation
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    today_str = now_local.strftime('%Y-%m-%d')

    return render_template('calendar/view.html',
                           calendar=cal, events=events, members=members,
                           view='month', selected_member_id=selected_member_id,
                           year=year, month=month, days_in_month=days_in_month,
                           first_weekday=first_weekday, events_by_date=events_by_date,
                           prev_year=prev_year, prev_month=prev_month,
                           next_year=next_year, next_month=next_month,
                           today_str=today_str,
                           month_name=cal_mod.month_name[month],
                           birthdays_by_date=birthdays_by_date,
                           holidays_by_date=holidays_by_date,
                           weather_by_date=weather_by_date,
                           create_event_url=_get_create_event_url(cal))


@main.route('/cal/<share_token>/week')
def calendar_week(share_token):
    """Week view."""
    cal = _get_calendar_or_404(share_token)

    # Determine which week to show (query param 'start' as YYYY-MM-DD, or current week)
    now_local = datetime.now(ZoneInfo(cal.timezone))
    start_str = request.args.get('start')
    if start_str:
        try:
            week_start = datetime.strptime(start_str, '%Y-%m-%d')
        except ValueError:
            week_start = now_local - timedelta(days=now_local.weekday())  # Monday
    else:
        week_start = now_local - timedelta(days=now_local.weekday())  # Monday

    week_dates = [(week_start + timedelta(days=i)) for i in range(7)]
    events_by_date = event_service.get_events_for_week(
        cal, week_start.year, week_start.month, week_start.day)
    events = event_service.get_upcoming_events(cal, limit=50)
    members = member_service.get_active_members(cal)
    selected_member_id = session.get(f'member_{share_token}')

    # Overlay data (birthdays, holidays, weather)
    ws_date = week_start.date()
    birthdays_by_date, holidays_by_date, weather_by_date = _get_calendar_overlays(
        cal, ws_date, ws_date + timedelta(days=7))

    prev_week = (week_start - timedelta(days=7)).strftime('%Y-%m-%d')
    next_week = (week_start + timedelta(days=7)).strftime('%Y-%m-%d')
    today_str = now_local.strftime('%Y-%m-%d')

    return render_template('calendar/view.html',
                           calendar=cal, events=events, members=members,
                           view='week', selected_member_id=selected_member_id,
                           week_dates=week_dates, events_by_date=events_by_date,
                           prev_week=prev_week, next_week=next_week,
                           today_str=today_str,
                           birthdays_by_date=birthdays_by_date,
                           holidays_by_date=holidays_by_date,
                           weather_by_date=weather_by_date,
                           create_event_url=_get_create_event_url(cal))
@main.route('/cal/<share_token>/agenda')
def calendar_agenda(share_token):
    """Agenda/list view."""
    cal = _get_calendar_or_404(share_token)
    events = event_service.get_upcoming_events(cal, limit=50)
    members = member_service.get_active_members(cal)
    selected_member_id = session.get(f'member_{share_token}')

    upcoming_birthdays = []
    if cal.show_birthdays:
        upcoming_birthdays = member_service.get_upcoming_birthdays(cal)

    upcoming_holidays = []
    if cal.show_holidays:
        upcoming_holidays = holiday_service.get_upcoming_holidays(cal)

    upcoming_weather = []
    weather_by_date = {}
    if cal.show_weather:
        upcoming_weather = weather_service.get_upcoming_weather(cal)
        weather_by_date = {w['date_str']: w for w in upcoming_weather}

    return render_template('calendar/view.html',
                           calendar=cal, events=events, members=members,
                           view='agenda', selected_member_id=selected_member_id,
                           upcoming_birthdays=upcoming_birthdays,
                           upcoming_holidays=upcoming_holidays,
                           upcoming_weather=upcoming_weather,
                           weather_by_date=weather_by_date,
                           create_event_url=_get_create_event_url(cal))


# ── Admin Dashboard ──────────────────────────────────────


@main.route('/cal/<share_token>/admin/<admin_token>', methods=['GET', 'POST'])
def admin_dashboard(share_token, admin_token):
    """Admin dashboard with inline settings form."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        return redirect(url_for('main.admin_auth', share_token=share_token, admin_token=admin_token))

    # Store admin token in session so calendar views can offer "click to create"
    session[f'admin_token_{share_token}'] = admin_token

    # Default GET: redirect to calendar view (admin button will be shown there)
    if request.method == 'GET' and not request.args.get('dashboard'):
        return redirect(url_for('main.calendar_view', share_token=share_token))

    form = CalendarSettingsForm(obj=cal)
    form.holiday_country.choices = holiday_service.get_supported_countries()

    if form.validate_on_submit():
        calendar_service.update_calendar_settings(
            cal,
            name=form.name.data,
            description=form.description.data,
            timezone=form.timezone.data,
            default_view=form.default_view.data,
            week_start=int(form.week_start.data),
            time_format=form.time_format.data,
            date_format=form.date_format.data,
            embed_allowed=form.embed_allowed.data,
            show_birthdays=form.show_birthdays.data,
            show_holidays=form.show_holidays.data,
            holiday_country=form.holiday_country.data or None,
            show_weather=form.show_weather.data,
            weather_lat=_parse_float(form.weather_lat.data),
            weather_lon=_parse_float(form.weather_lon.data),
        )
        if form.admin_password.data:
            calendar_service.set_admin_password(cal, form.admin_password.data)

        flash('Settings saved.', 'success')
        return redirect(url_for('main.admin_dashboard',
                                share_token=share_token, admin_token=admin_token,
                                dashboard=1) + '#settings')

    events = event_service.get_upcoming_events(cal, limit=50)
    members = member_service.get_all_members(cal)
    audit_logs = audit_service.get_recent_logs(cal, limit=15)
    return render_template('admin/dashboard.html',
                           calendar=cal, events=events, members=members,
                           audit_logs=audit_logs, form=form)


@main.route('/cal/<share_token>/admin/<admin_token>/auth', methods=['GET', 'POST'])
def admin_auth(share_token, admin_token):
    """Password entry for password-protected admin access."""
    cal = _get_calendar_or_404(share_token)
    if not secrets.compare_digest(cal.admin_token, admin_token):
        abort(403)

    if not cal.admin_password_hash:
        # No password needed
        return redirect(url_for('main.admin_dashboard', share_token=share_token, admin_token=admin_token))

    form = AdminAuthForm()
    if form.validate_on_submit():
        if calendar_service.check_admin_password(cal, form.password.data):
            session[f'admin_auth_{admin_token}'] = True
            session.permanent = True
            return redirect(url_for('main.admin_dashboard', share_token=share_token, admin_token=admin_token))
        flash('Incorrect password.', 'error')

    return render_template('admin/auth.html', calendar=cal, form=form)


# ── Calendar Settings (redirect to dashboard) ───────────


@main.route('/cal/<share_token>/admin/<admin_token>/settings')
def calendar_settings(share_token, admin_token):
    """Redirect old settings URL to the unified admin dashboard."""
    return redirect(url_for('main.admin_dashboard',
                            share_token=share_token, admin_token=admin_token) + '#settings', code=301)


@main.route('/cal/<share_token>/admin/<admin_token>/delete', methods=['POST'])
def delete_calendar(share_token, admin_token):
    """Delete a calendar."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    calendar_service.delete_calendar(cal)
    flash('Calendar deleted.', 'success')
    return redirect(url_for('main.index'))


@main.route('/cal/<share_token>/admin/<admin_token>/regenerate-tokens', methods=['POST'])
def regenerate_tokens(share_token, admin_token):
    """Regenerate all access tokens (share, manager, admin) in case of compromise."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    new_tokens = calendar_service.regenerate_all_tokens(cal)

    # Clear old session auth (admin_token changed)
    session.pop(f'admin_auth_{admin_token}', None)
    session.pop(f'admin_token_{share_token}', None)

    # Send email with new tokens if owner email is set
    base_url = current_app.config['BASE_URL']
    new_share = new_tokens['share_token']
    new_manager = new_tokens['manager_token']
    new_admin = new_tokens['admin_token']

    share_url = f"{base_url}/cal/{new_share}"
    manager_url = f"{base_url}/cal/{new_share}/manage/{new_manager}"
    admin_url = f"{base_url}/cal/{new_share}/admin/{new_admin}"

    if cal.owner_email:
        email_service.send_regenerated_tokens_email(
            cal.owner_email, cal.name, share_url, manager_url, admin_url
        )
        flash('All tokens regenerated. New links have been emailed to you.', 'success')
    else:
        flash('All tokens regenerated. No email on file — bookmark your new admin link now!', 'warning')

    # Store new admin token in session
    session[f'admin_token_{new_share}'] = new_admin

    return redirect(url_for('main.admin_dashboard',
                            share_token=new_share, admin_token=new_admin))


# ── Member Management (Admin) ────────────────────────────


@main.route('/cal/<share_token>/admin/<admin_token>/members')
def members_list(share_token, admin_token):
    """Member management page."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        return redirect(url_for('main.admin_auth', share_token=share_token, admin_token=admin_token))

    members = member_service.get_all_members(cal)
    form = MemberForm()
    icon_form = MemberIconForm()
    return render_template('admin/members.html',
                           calendar=cal, members=members, form=form, icon_form=icon_form)


@main.route('/cal/<share_token>/admin/<admin_token>/members/add', methods=['POST'])
def add_member(share_token, admin_token):
    """Add a new member."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    form = MemberForm()
    if form.validate_on_submit():
        birthday = _parse_birthday(request.form.get('birthday'))
        member_service.add_member(cal, name=form.name.data, color=form.color.data, birthday=birthday)
        flash('Member added.', 'success')

    return redirect(url_for('main.members_list', share_token=share_token, admin_token=admin_token))


@main.route('/cal/<share_token>/admin/<admin_token>/members/<member_id>/edit', methods=['POST'])
def edit_member(share_token, admin_token, member_id):
    """Edit a member."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    member = member_service.get_member_by_id(_parse_uuid(member_id))
    if not member or member.calendar_id != cal.id:
        abort(404)

    form = MemberForm()
    if form.validate_on_submit():
        birthday = _parse_birthday(request.form.get('birthday'))
        member_service.update_member(member, name=form.name.data, color=form.color.data, birthday=birthday)
        flash('Member updated.', 'success')

    return redirect(url_for('main.members_list', share_token=share_token, admin_token=admin_token))


@main.route('/cal/<share_token>/admin/<admin_token>/members/<member_id>/icon', methods=['POST'])
def upload_member_icon(share_token, admin_token, member_id):
    """Upload a member avatar icon."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    member = member_service.get_member_by_id(_parse_uuid(member_id))
    if not member or member.calendar_id != cal.id:
        abort(404)

    form = MemberIconForm()
    if form.validate_on_submit():
        member_service.process_avatar_upload(
            member, form.icon.data, current_app.config['UPLOAD_DIR']
        )
        flash('Avatar uploaded.', 'success')
    else:
        flash('Invalid image file.', 'error')

    return redirect(url_for('main.members_list', share_token=share_token, admin_token=admin_token))


@main.route('/cal/<share_token>/admin/<admin_token>/members/<member_id>/deactivate', methods=['POST'])
def deactivate_member(share_token, admin_token, member_id):
    """Soft-delete a member."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    member = member_service.get_member_by_id(_parse_uuid(member_id))
    if not member or member.calendar_id != cal.id:
        abort(404)

    if member.is_active:
        member_service.deactivate_member(member)
        flash('Member deactivated.', 'success')
    else:
        member_service.reactivate_member(member)
        flash('Member reactivated.', 'success')

    return redirect(url_for('main.members_list', share_token=share_token, admin_token=admin_token))


# ── Tag Management (Admin) ─────────────────────────────────

@main.route('/cal/<share_token>/admin/<admin_token>/tags')
def tags_list(share_token, admin_token):
    """Tag management page."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        return redirect(url_for('main.admin_auth', share_token=share_token, admin_token=admin_token))

    tags = tag_service.get_tags_for_calendar(cal)
    form = TagForm()
    return render_template('admin/tags.html', calendar=cal, tags=tags, form=form)


@main.route('/cal/<share_token>/admin/<admin_token>/tags/add', methods=['POST'])
def add_tag(share_token, admin_token):
    """Add a new tag."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    form = TagForm()
    if form.validate_on_submit():
        tag_service.create_tag(cal, form.name.data, form.color.data or '#16a34a')
        flash('Tag added.', 'success')
    return redirect(url_for('main.tags_list', share_token=share_token, admin_token=admin_token))


@main.route('/cal/<share_token>/admin/<admin_token>/tags/<tag_id>/edit', methods=['POST'])
def edit_tag(share_token, admin_token, tag_id):
    """Edit a tag."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    tag = tag_service.get_tag_by_id(_parse_uuid(tag_id), cal)
    if not tag:
        abort(404)

    tag_service.update_tag(tag, name=request.form.get('name'), color=request.form.get('color'))
    flash('Tag updated.', 'success')
    return redirect(url_for('main.tags_list', share_token=share_token, admin_token=admin_token))


@main.route('/cal/<share_token>/admin/<admin_token>/tags/<tag_id>/delete', methods=['POST'])
def delete_tag(share_token, admin_token, tag_id):
    """Delete a tag."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    tag = tag_service.get_tag_by_id(_parse_uuid(tag_id), cal)
    if not tag:
        abort(404)

    tag_service.delete_tag(tag)
    flash('Tag deleted.', 'success')
    return redirect(url_for('main.tags_list', share_token=share_token, admin_token=admin_token))


# ── Events (Admin CRUD) ─────────────────────────────────


@main.route('/cal/<share_token>/admin/<admin_token>/event/new', methods=['GET', 'POST'])
def create_event(share_token, admin_token):
    """Create a new event."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        return redirect(url_for('main.admin_auth', share_token=share_token, admin_token=admin_token))

    form = EventForm()
    tags = tag_service.get_tags_for_calendar(cal)

    # Prefill date from query param (click-to-create from calendar view)
    if request.method == 'GET' and request.args.get('date'):
        form.start_date.data = request.args['date']

    if form.validate_on_submit():
        start_dt = _parse_event_datetime(form.start_date.data, request.form.get('start_time'))
        end_dt = _parse_event_datetime(form.end_date.data, request.form.get('end_time'))

        if not start_dt:
            flash('Invalid start date/time.', 'error')
            return render_template('event/form.html', calendar=cal, form=form, editing=False, tags=tags)

        event = event_service.create_event(
            calendar=cal,
            title=form.title.data,
            start_time_local=start_dt,
            end_time_local=end_dt,
            all_day=form.all_day.data,
            description=form.description.data,
            location=form.location.data,
            location_url=form.location_url.data,
            whatsapp_url=form.whatsapp_url.data,
        )
        # Assign selected tags
        selected_tag_ids = request.form.getlist('tags')
        if selected_tag_ids:
            tag_service.set_event_tags(event, selected_tag_ids, cal)

        audit_service.log_action(cal, 'event.created', f'"{event.title}"')
        flash('Event created.', 'success')
        return redirect(url_for('main.admin_dashboard',
                                share_token=share_token, admin_token=admin_token))

    return render_template('event/form.html', calendar=cal, form=form, editing=False, tags=tags)


@main.route('/cal/<share_token>/admin/<admin_token>/event/<event_id>/edit', methods=['GET', 'POST'])
def edit_event(share_token, admin_token, event_id):
    """Edit an existing event."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        return redirect(url_for('main.admin_auth', share_token=share_token, admin_token=admin_token))

    event = event_service.get_event_by_id(_parse_uuid(event_id))
    if not event or event.calendar_id != cal.id:
        abort(404)

    form = EventForm(obj=event)
    tags = tag_service.get_tags_for_calendar(cal)
    selected_tag_ids = [str(t.id) for t in event.tags]

    if request.method == 'GET':
        # Pre-fill datetime fields in local time
        from app.utils import utc_to_local
        local_start = utc_to_local(event.start_time, cal.timezone)
        form.start_date.data = local_start.strftime('%Y-%m-%d')
        form.start_time_val = local_start.strftime('%H:%M')
        if event.end_time:
            local_end = utc_to_local(event.end_time, cal.timezone)
            form.end_date.data = local_end.strftime('%Y-%m-%d')
            form.end_time_val = local_end.strftime('%H:%M')

    if form.validate_on_submit():
        start_dt = _parse_event_datetime(form.start_date.data, request.form.get('start_time'))
        end_dt = _parse_event_datetime(form.end_date.data, request.form.get('end_time'))

        if not start_dt:
            flash('Invalid start date/time.', 'error')
            return render_template('event/form.html', calendar=cal, form=form,
                                   event=event, editing=True, tags=tags, selected_tag_ids=selected_tag_ids)

        event_service.update_event(
            event, cal,
            title=form.title.data,
            description=form.description.data,
            start_time_local=start_dt,
            end_time_local=end_dt,
            all_day=form.all_day.data,
            location=form.location.data,
            location_url=form.location_url.data,
            whatsapp_url=form.whatsapp_url.data,
        )
        # Update tags
        tag_service.set_event_tags(event, request.form.getlist('tags'), cal)

        audit_service.log_action(cal, 'event.updated', f'"{event.title}"')
        flash('Event updated.', 'success')
        return redirect(url_for('main.admin_dashboard',
                                share_token=share_token, admin_token=admin_token))

    return render_template('event/form.html', calendar=cal, form=form,
                           event=event, editing=True, tags=tags, selected_tag_ids=selected_tag_ids)


@main.route('/cal/<share_token>/admin/<admin_token>/event/<event_id>/delete', methods=['POST'])
def delete_event(share_token, admin_token, event_id):
    """Delete an event."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    event = event_service.get_event_by_id(_parse_uuid(event_id))
    if not event or event.calendar_id != cal.id:
        abort(404)

    event_title = event.title
    event_service.delete_event(event)
    audit_service.log_action(cal, 'event.deleted', f'"{event_title}"')
    flash('Event deleted.', 'success')
    return redirect(url_for('main.admin_dashboard',
                            share_token=share_token, admin_token=admin_token))


@main.route('/cal/<share_token>/admin/<admin_token>/event/<event_id>/duplicate', methods=['POST'])
def duplicate_event_admin(share_token, admin_token, event_id):
    """Duplicate an event (admin)."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    event = event_service.get_event_by_id(_parse_uuid(event_id))
    if not event or event.calendar_id != cal.id:
        abort(404)

    new_event = event_service.duplicate_event(event, cal)
    flash(f'Duplicated "{event.title}". Edit the copy to change the date.', 'success')
    return redirect(url_for('main.edit_event',
                            share_token=share_token, admin_token=admin_token,
                            event_id=new_event.id))


@main.route('/cal/<share_token>/admin/<admin_token>/event/<event_id>/bulk-rsvp', methods=['POST'])
def bulk_rsvp(share_token, admin_token, event_id):
    """Set all active members to a given RSVP status (admin only)."""
    cal, authenticated = _require_admin(share_token, admin_token)
    if not authenticated:
        abort(403)

    event = event_service.get_event_by_id(_parse_uuid(event_id))
    if not event or event.calendar_id != cal.id:
        abort(404)

    status = request.form.get('status', 'in')
    if status not in ('in', 'maybe', 'out'):
        flash('Invalid RSVP status.', 'error')
        return redirect(url_for('main.admin_dashboard', share_token=share_token, admin_token=admin_token))

    members = member_service.get_active_members(cal)
    count = rsvp_service.bulk_set_rsvp(event, members, status)
    audit_service.log_action(cal, 'rsvp.bulk_set', f'Set {count} members → {status} for "{event.title}"')
    flash(f'Set {count} members to "{status}" for "{event.title}".', 'success')
    return redirect(url_for('main.admin_dashboard', share_token=share_token, admin_token=admin_token))


# ── Manager Dashboard + Event CRUD ───────────────────


@main.route('/cal/<share_token>/manage/<manager_token>')
def manager_dashboard(share_token, manager_token):
    """Manager dashboard — event CRUD without member/calendar management."""
    cal = _require_manager(share_token, manager_token)

    # Store manager token in session so calendar views can offer "click to create"
    session[f'manager_token_{share_token}'] = manager_token

    events = event_service.get_upcoming_events(cal, limit=50)
    members = member_service.get_active_members(cal)
    return render_template('admin/manager.html',
                           calendar=cal, events=events, members=members,
                           manager_token=manager_token)


@main.route('/cal/<share_token>/manage/<manager_token>/event/new', methods=['GET', 'POST'])
def manager_create_event(share_token, manager_token):
    """Create a new event (manager access)."""
    cal = _require_manager(share_token, manager_token)

    form = EventForm()
    tags = tag_service.get_tags_for_calendar(cal)

    # Prefill date from query param (click-to-create from calendar view)
    if request.method == 'GET' and request.args.get('date'):
        form.start_date.data = request.args['date']

    if form.validate_on_submit():
        start_dt = _parse_event_datetime(form.start_date.data, request.form.get('start_time'))
        end_dt = _parse_event_datetime(form.end_date.data, request.form.get('end_time'))

        if not start_dt:
            flash('Invalid start date/time.', 'error')
            return render_template('event/form.html', calendar=cal, form=form,
                                   editing=False, manager_token=manager_token, tags=tags)

        event = event_service.create_event(
            calendar=cal,
            title=form.title.data,
            start_time_local=start_dt,
            end_time_local=end_dt,
            all_day=form.all_day.data,
            description=form.description.data,
            location=form.location.data,
            location_url=form.location_url.data,
            whatsapp_url=form.whatsapp_url.data,
        )
        selected_tag_ids = request.form.getlist('tags')
        if selected_tag_ids:
            tag_service.set_event_tags(event, selected_tag_ids, cal)

        flash('Event created.', 'success')
        return redirect(url_for('main.manager_dashboard',
                                share_token=share_token, manager_token=manager_token))

    return render_template('event/form.html', calendar=cal, form=form,
                           editing=False, manager_token=manager_token, tags=tags)


@main.route('/cal/<share_token>/manage/<manager_token>/event/<event_id>/edit', methods=['GET', 'POST'])
def manager_edit_event(share_token, manager_token, event_id):
    """Edit an existing event (manager access)."""
    cal = _require_manager(share_token, manager_token)

    event = event_service.get_event_by_id(_parse_uuid(event_id))
    if not event or event.calendar_id != cal.id:
        abort(404)

    form = EventForm(obj=event)
    tags = tag_service.get_tags_for_calendar(cal)
    selected_tag_ids = [str(t.id) for t in event.tags]

    if request.method == 'GET':
        from app.utils import utc_to_local
        local_start = utc_to_local(event.start_time, cal.timezone)
        form.start_date.data = local_start.strftime('%Y-%m-%d')
        form.start_time_val = local_start.strftime('%H:%M')
        if event.end_time:
            local_end = utc_to_local(event.end_time, cal.timezone)
            form.end_date.data = local_end.strftime('%Y-%m-%d')
            form.end_time_val = local_end.strftime('%H:%M')

    if form.validate_on_submit():
        start_dt = _parse_event_datetime(form.start_date.data, request.form.get('start_time'))
        end_dt = _parse_event_datetime(form.end_date.data, request.form.get('end_time'))

        if not start_dt:
            flash('Invalid start date/time.', 'error')
            return render_template('event/form.html', calendar=cal, form=form,
                                   event=event, editing=True, manager_token=manager_token,
                                   tags=tags, selected_tag_ids=selected_tag_ids)

        event_service.update_event(
            event, cal,
            title=form.title.data,
            description=form.description.data,
            start_time_local=start_dt,
            end_time_local=end_dt,
            all_day=form.all_day.data,
            location=form.location.data,
            location_url=form.location_url.data,
            whatsapp_url=form.whatsapp_url.data,
        )
        tag_service.set_event_tags(event, request.form.getlist('tags'), cal)

        flash('Event updated.', 'success')
        return redirect(url_for('main.manager_dashboard',
                                share_token=share_token, manager_token=manager_token))

    return render_template('event/form.html', calendar=cal, form=form,
                           event=event, editing=True, manager_token=manager_token,
                           tags=tags, selected_tag_ids=selected_tag_ids)


@main.route('/cal/<share_token>/manage/<manager_token>/event/<event_id>/delete', methods=['POST'])
def manager_delete_event(share_token, manager_token, event_id):
    """Delete an event (manager access)."""
    cal = _require_manager(share_token, manager_token)

    event = event_service.get_event_by_id(_parse_uuid(event_id))
    if not event or event.calendar_id != cal.id:
        abort(404)

    event_service.delete_event(event)
    flash('Event deleted.', 'success')
    return redirect(url_for('main.manager_dashboard',
                            share_token=share_token, manager_token=manager_token))


@main.route('/cal/<share_token>/manage/<manager_token>/event/<event_id>/duplicate', methods=['POST'])
def duplicate_event_manager(share_token, manager_token, event_id):
    """Duplicate an event (manager)."""
    cal = _require_manager(share_token, manager_token)

    event = event_service.get_event_by_id(_parse_uuid(event_id))
    if not event or event.calendar_id != cal.id:
        abort(404)

    new_event = event_service.duplicate_event(event, cal)
    flash(f'Duplicated "{event.title}". Edit the copy to change the date.', 'success')
    return redirect(url_for('main.manager_edit_event',
                            share_token=share_token, manager_token=manager_token,
                            event_id=new_event.id))

# ── Event Views (Read-Only) ─────────────────────────────


@main.route('/cal/<share_token>/event/<event_id>')
def event_detail(share_token, event_id):
    """View event detail within calendar context."""
    cal = _get_calendar_or_404(share_token)
    event = event_service.get_event_by_id(_parse_uuid(event_id))
    if not event or event.calendar_id != cal.id:
        abort(404)

    rsvp_data = rsvp_service.get_rsvps_for_event(event)
    members = member_service.get_active_members(cal)
    selected_member_id = session.get(f'member_{share_token}')
    my_rsvp = None
    if selected_member_id:
        my_rsvp = rsvp_service.get_member_rsvp(event.id, selected_member_id)

    # Build edit URL if session has admin/manager tokens
    edit_url = None
    share = cal.share_token
    admin_tok = session.get(f'admin_token_{share}')
    mgr_tok = session.get(f'manager_token_{share}')
    if admin_tok:
        edit_url = url_for('main.edit_event', share_token=share,
                           admin_token=admin_tok, event_id=event.id)
    elif mgr_tok:
        edit_url = url_for('main.manager_edit_event', share_token=share,
                           manager_token=mgr_tok, event_id=event.id)

    return render_template('event/detail.html',
                           calendar=cal, event=event, rsvp_data=rsvp_data,
                           members=members, selected_member_id=selected_member_id,
                           my_rsvp=my_rsvp, edit_url=edit_url)


@main.route('/event/<event_share_token>')
def event_standalone(event_share_token):
    """Standalone shareable event link (no calendar context needed)."""
    event = event_service.get_event_by_share_token(event_share_token)
    if not event:
        abort(404)

    cal = event.calendar
    rsvp_data = rsvp_service.get_rsvps_for_event(event)
    members = member_service.get_active_members(cal)

    return render_template('event/detail_standalone.html',
                           calendar=cal, event=event, rsvp_data=rsvp_data,
                           members=members)


# ── RSVP API ─────────────────────────────────────────────


@main.route('/api/cal/<share_token>/event/<event_id>/rsvp', methods=['POST'])
def api_set_rsvp(share_token, event_id):
    """Set RSVP via JSON API."""
    cal = _get_calendar_or_404(share_token)
    event = event_service.get_event_by_id(_parse_uuid(event_id))
    if not event or event.calendar_id != cal.id:
        return jsonify(error='Event not found'), 404

    data = request.get_json(silent=True) or {}
    member_id_str = data.get('member_id')
    status = data.get('status')

    if not member_id_str or not status:
        return jsonify(error='member_id and status required'), 400

    if status not in ('in', 'maybe', 'out'):
        return jsonify(error='Invalid status. Use: in, maybe, out'), 400

    member_id = _parse_uuid(member_id_str)
    member = member_service.get_member_by_id(member_id)
    if not member or member.calendar_id != cal.id:
        return jsonify(error='Member not found'), 404

    rsvp = rsvp_service.set_rsvp(event.id, member.id, status)
    audit_service.log_action(cal, 'rsvp.changed', f'{member.name} → {status} for "{event.title}"')

    # Remember selected member in session
    session[f'member_{share_token}'] = str(member.id)
    session.permanent = True

    return jsonify(
        ok=True,
        member_id=str(member.id),
        event_id=str(event.id),
        status=rsvp.status,
    )


@main.route('/api/cal/<share_token>/event/<event_id>/rsvp', methods=['GET'])
def api_get_rsvps(share_token, event_id):
    """Get RSVPs for an event as JSON."""
    cal = _get_calendar_or_404(share_token)
    event = event_service.get_event_by_id(_parse_uuid(event_id))
    if not event or event.calendar_id != cal.id:
        return jsonify(error='Event not found'), 404

    rsvp_data = rsvp_service.get_rsvps_for_event(event)

    def _member_json(m):
        return {'id': str(m.id), 'name': m.name, 'color': m.color, 'avatar_url': m.avatar_url}

    return jsonify(
        event_id=str(event.id),
        rsvps={
            'in': [_member_json(m) for m in rsvp_data['in']],
            'maybe': [_member_json(m) for m in rsvp_data['maybe']],
            'out': [_member_json(m) for m in rsvp_data['out']],
            'no_response': [_member_json(m) for m in rsvp_data['no_response']],
        },
    )


# ── iCal Feed ────────────────────────────────────────────


@main.route('/cal/<share_token>/feed.ics')
def ical_feed(share_token):
    """Generate iCal feed for Outlook/Google Calendar subscription."""
    cal = _get_calendar_or_404(share_token)
    ical_bytes = feed_service.generate_ical_feed(cal)

    response = make_response(ical_bytes)
    response.headers['Content-Type'] = 'text/calendar; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="{cal.name}.ics"'
    response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    return response


# ── Embed View ───────────────────────────────────────────


@main.route('/cal/<share_token>/embed')
def calendar_embed(share_token):
    """Embeddable calendar view (no header/footer)."""
    cal = _get_calendar_or_404(share_token)
    if not cal.embed_allowed:
        abort(403)

    events = event_service.get_upcoming_events(cal, limit=50)
    members = member_service.get_active_members(cal)

    upcoming_birthdays = []
    if cal.show_birthdays:
        upcoming_birthdays = member_service.get_upcoming_birthdays(cal)

    upcoming_holidays = []
    if cal.show_holidays:
        upcoming_holidays = holiday_service.get_upcoming_holidays(cal)

    upcoming_weather = []
    weather_by_date = {}
    if cal.show_weather:
        upcoming_weather = weather_service.get_upcoming_weather(cal)
        weather_by_date = {w['date_str']: w for w in upcoming_weather}

    return render_template('calendar/embed.html',
                           calendar=cal, events=events, members=members,
                           view='agenda', upcoming_birthdays=upcoming_birthdays,
                           upcoming_holidays=upcoming_holidays,
                           upcoming_weather=upcoming_weather,
                           weather_by_date=weather_by_date)


@main.route('/cal/<share_token>/qr.png')
def calendar_qr(share_token):
    """Generate QR code PNG for a calendar URL.

    Accepts an optional ?url= parameter to encode a specific link (must start
    with the app's BASE_URL for safety).  Defaults to the read-only share URL.
    """
    import io
    import qrcode

    cal = _get_calendar_or_404(share_token)
    base = current_app.config['BASE_URL'].rstrip('/')
    target_url = request.args.get('url', '').strip()

    # Safety: only allow URLs that belong to this app
    if not target_url or not target_url.startswith(base):
        target_url = f"{base}/cal/{cal.share_token}"

    img = qrcode.make(target_url, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    response = make_response(buf.read())
    response.headers['Content-Type'] = 'image/png'
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response


# ── Uploads ──────────────────────────────────────────────


@main.route('/uploads/avatars/<filename>')
def uploaded_avatar(filename):
    """Serve uploaded avatar images."""
    response = serve_avatar(filename)
    response.headers['Cache-Control'] = 'public, max-age=86400'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


# ── JSON API (for integration) ───────────────────────────


@main.route('/api/cal/<share_token>/events')
def api_events(share_token):
    """Get events as JSON for external integration."""
    cal = _get_calendar_or_404(share_token)

    # Optional date range params
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    limit = request.args.get('limit', 50, type=int)

    start = None
    end = None
    if start_str:
        try:
            start = datetime.fromisoformat(start_str)
        except ValueError:
            pass
    if end_str:
        try:
            end = datetime.fromisoformat(end_str)
        except ValueError:
            pass

    events = event_service.get_events_for_calendar(cal, start=start, end=end, limit=limit)

    return jsonify(
        calendar={'id': str(cal.id), 'name': cal.name, 'timezone': cal.timezone},
        events=[{
            'id': str(e.id),
            'title': e.title,
            'description': e.description,
            'start_time': e.start_time.isoformat(),
            'end_time': e.end_time.isoformat() if e.end_time else None,
            'all_day': e.all_day,
            'location': e.location,
            'location_url': e.location_url,
            'whatsapp_url': e.whatsapp_url,
            'share_token': e.share_token,
            'rsvp_summary': e.rsvp_summary,
        } for e in events],
    )


@main.route('/api/cal/<share_token>/info')
def api_calendar_info(share_token):
    """Get calendar metadata as JSON."""
    cal = _get_calendar_or_404(share_token)
    return jsonify(
        id=str(cal.id),
        name=cal.name,
        description=cal.description,
        timezone=cal.timezone,
        default_view=cal.default_view,
        member_count=len([m for m in cal.members if m.is_active]),
    )


@main.route('/api/calendars/validate', methods=['POST'])
def api_validate_calendars():
    """Validate a list of share tokens, return which still exist with current names.

    Also accepts admin_tokens dict {share_token: admin_token} to verify admin access.
    Returns admin_valid=true for entries whose admin_token still matches.
    """
    data = request.get_json(silent=True) or {}
    tokens = data.get('tokens', [])
    admin_tokens = data.get('admin_tokens', {})  # {share_token: admin_token}
    if not isinstance(tokens, list) or len(tokens) > 50:
        return jsonify(error='Invalid request'), 400
    result = {}
    for token in tokens:
        cal = calendar_service.get_calendar_by_share_token(token)
        if cal:
            entry = {'name': cal.name}
            # Verify admin token if provided
            claimed_admin = admin_tokens.get(token)
            if claimed_admin and secrets.compare_digest(cal.admin_token, claimed_admin):
                entry['admin_valid'] = True
            result[token] = entry
    return jsonify(result)


@main.route('/api/cal/<share_token>/members')
def api_members(share_token):
    """Get active members as JSON."""
    cal = _get_calendar_or_404(share_token)
    members = sorted(
        [m for m in cal.members if m.is_active],
        key=lambda m: m.sort_order,
    )
    return jsonify(
        calendar={'id': str(cal.id), 'name': cal.name},
        members=[{
            'id': str(m.id),
            'name': m.name,
            'initials': m.initials,
            'color': m.color,
            'avatar_url': m.avatar_url,
        } for m in members],
    )


@main.route('/api/cal/<share_token>/next-event')
def api_next_event(share_token):
    """Get the next upcoming event as JSON (for countdown widget)."""
    cal = _get_calendar_or_404(share_token)
    events = event_service.get_upcoming_events(cal, limit=1)
    if not events:
        return jsonify(calendar={'id': str(cal.id), 'name': cal.name, 'timezone': cal.timezone}, event=None)

    e = events[0]
    return jsonify(
        calendar={'id': str(cal.id), 'name': cal.name, 'timezone': cal.timezone, 'date_format': cal.date_format, 'time_format': cal.time_format},
        event={
            'id': str(e.id),
            'title': e.title,
            'start_time': e.start_time.isoformat(),
            'end_time': e.end_time.isoformat() if e.end_time else None,
            'all_day': e.all_day,
            'location': e.location,
            'share_token': e.share_token,
            'rsvp_summary': e.rsvp_summary,
        },
    )
