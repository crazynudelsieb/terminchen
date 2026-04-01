"""Email sending service using SMTP."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

logger = logging.getLogger(__name__)


def _send_smtp(msg, to_email):
    """Send a MIME message via SMTP.  Returns True on success, False on failure."""
    cfg = current_app.config
    host = cfg['SMTP_HOST']
    port = cfg['SMTP_PORT']
    use_tls = cfg['SMTP_USE_TLS']
    user = cfg['SMTP_USER']
    password = cfg['SMTP_PASSWORD']
    from_email = cfg['SMTP_FROM_EMAIL']

    try:
        if use_tls:
            server = smtplib.SMTP(host, port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP(host, port, timeout=15)

        if user and password:
            server.login(user, password)

        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as exc:
        logger.error("email.send_failed", extra={"to": to_email, "error": str(exc)})
        return False


def is_email_configured():
    """Check whether SMTP settings are filled in."""
    return bool(current_app.config.get('SMTP_HOST'))


def _build_and_send(to_email, subject, text_body, html_content, log_event, log_extra=None):
    """Build a MIME email with shared dark-theme wrapper and send via SMTP.

    Args:
        to_email: Recipient address
        subject: Email subject line
        text_body: Plain-text body (full)
        html_content: Inner HTML content (inserted into the shared wrapper)
        log_event: Logger event name on success
        log_extra: Optional dict of extra log fields

    Returns True on success, False on failure.
    """
    if not is_email_configured():
        logger.warning("email.skip: SMTP not configured")
        return False

    cfg = current_app.config
    from_name = cfg['SMTP_FROM_NAME']
    from_email = cfg['SMTP_FROM_EMAIL']

    # Shared dark-theme HTML wrapper
    html_body = (
        '<html>'
        '<body style="font-family:Inter,system-ui,sans-serif;background:#111827;color:#f8fafc;padding:24px;">'
        '  <div style="max-width:600px;margin:0 auto;background:#1e293b;border-radius:12px;padding:24px;">'
        f'    {html_content}'
        '  </div>'
        '</body>'
        '</html>'
    )

    msg = MIMEMultipart('alternative')
    msg['From'] = f"{from_name} <{from_email}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    if _send_smtp(msg, to_email):
        logger.info(log_event, extra=log_extra or {})
        return True
    return False


def _html_link_section(label, url, color='#16a34a'):
    """Build an HTML section with heading + link."""
    return (
        f'<h3 style="color:#cbd5e1;">{label}</h3>'
        f'<p><a href="{url}" style="color:{color};">{url}</a></p>'
    )


_HTML_HR = '<hr style="border:none;border-top:1px solid #334155;margin:24px 0;">'
_HTML_FOOTER_STYLE = 'color:#94a3b8;font-size:0.85rem;'


def send_calendar_links(to_email, calendar_name, share_url, manager_url, admin_url):
    """Send the calendar access links to the owner's email address."""
    from_name = current_app.config['SMTP_FROM_NAME']

    text_body = (
        f"Hi!\n\n"
        f"Your calendar \"{calendar_name}\" has been created.\n\n"
        f"Bookmark these links — they are the only way to access your calendar.\n\n"
        f"📅  View (read-only, share this):\n{share_url}\n\n"
        f"📝  Manager (can create events):\n{manager_url}\n\n"
        f"🔑  Admin (full control):\n{admin_url}\n\n"
        f"Keep the admin link private!\n\n"
        f"— {from_name}\n"
    )

    html_content = (
        f'<h1 style="color:#16a34a;margin-top:0;">📅 {calendar_name}</h1>'
        '<p>Your calendar has been created! Bookmark these links — they are the only way to access your calendar.</p>'
        + _html_link_section('📅 View (read-only, share this)', share_url)
        + _html_link_section('📝 Manager (can create events)', manager_url, '#f59e0b')
        + _html_link_section('🔑 Admin (full control)', admin_url, '#dc2626')
        + _HTML_HR
        + f'<p style="{_HTML_FOOTER_STYLE}">Keep the admin link private! Anyone with it has full control over your calendar.</p>'
    )

    return _build_and_send(
        to_email, f"Your calendar links — {calendar_name}",
        text_body, html_content, "email.sent",
        {"to": to_email, "calendar": calendar_name},
    )


def send_recovery_email(to_email, calendars, base_url):
    """Send a recovery email listing all calendars linked to this email."""
    cfg = current_app.config
    from_name = cfg['SMTP_FROM_NAME']
    subject = f"Your {cfg['APP_NAME']} calendar links"

    # ── Plain-text body ──
    lines = [
        "Hi!\n",
        f"Here are all the calendars linked to {to_email}:\n",
    ]
    for cal in calendars:
        admin_url = f"{base_url}/cal/{cal.share_token}/admin/{cal.admin_token}"
        lines.append(f"  🔑 {cal.name}\n     {admin_url}\n")
    lines.append(f"\nKeep these links private!\n\n— {from_name}\n")
    text_body = "\n".join(lines)

    # ── HTML content ──
    cal_rows = ""
    for cal in calendars:
        admin_url = f"{base_url}/cal/{cal.share_token}/admin/{cal.admin_token}"
        cal_rows += (
            '<div style="background:#111827;border-radius:8px;padding:12px 16px;margin-bottom:8px;">'
            f'  <strong style="color:#f8fafc;">{cal.name}</strong>'
            f'  <br><a href="{admin_url}" style="color:#16a34a;font-size:0.9rem;">{admin_url}</a>'
            '</div>'
        )

    html_content = (
        '<h1 style="color:#16a34a;margin-top:0;">🔑 Calendar Recovery</h1>'
        f'<p>Here are all calendars linked to <strong>{to_email}</strong>:</p>'
        + cal_rows
        + _HTML_HR
        + f'<p style="{_HTML_FOOTER_STYLE}">Keep these links private! Anyone with an admin link has full control.</p>'
    )

    return _build_and_send(
        to_email, subject, text_body, html_content, "email.recovery_sent",
        {"to": to_email, "count": len(calendars)},
    )


def send_regenerated_tokens_email(to_email, calendar_name, share_url, manager_url, admin_url):
    """Send an email with the new tokens after a token regeneration."""
    from_name = current_app.config['SMTP_FROM_NAME']

    text_body = (
        f"Hi!\n\n"
        f"All access tokens for your calendar \"{calendar_name}\" have been regenerated.\n\n"
        f"⚠️  All previous links are now INVALID.\n\n"
        f"Here are your new links:\n\n"
        f"📅  View (read-only, share this):\n{share_url}\n\n"
        f"📝  Manager (can create events):\n{manager_url}\n\n"
        f"🔑  Admin (full control):\n{admin_url}\n\n"
        f"If you did not request this, someone with admin access regenerated the tokens.\n\n"
        f"— {from_name}\n"
    )

    html_content = (
        '<h1 style="color:#dc2626;margin-top:0;">⚠️ Tokens Regenerated</h1>'
        f'<p>All access tokens for <strong>{calendar_name}</strong> have been regenerated. '
        'All previous links are now <strong>invalid</strong>.</p>'
        + _html_link_section('📅 View (read-only)', share_url)
        + _html_link_section('📝 Manager', manager_url, '#f59e0b')
        + _html_link_section('🔑 Admin (full control)', admin_url, '#dc2626')
        + _HTML_HR
        + f'<p style="{_HTML_FOOTER_STYLE}">'
        'If you did not request this change, someone with admin access regenerated the tokens. '
        'Bookmark the new admin link above to retain access.</p>'
    )

    return _build_and_send(
        to_email, f"⚠️ New access links — {calendar_name}",
        text_body, html_content, "email.tokens_regenerated_sent",
        {"to": to_email, "calendar": calendar_name},
    )
