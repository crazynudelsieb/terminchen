"""Email sending service using SMTP."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

logger = logging.getLogger(__name__)


def is_email_configured():
    """Check whether SMTP settings are filled in."""
    return bool(current_app.config.get('SMTP_HOST'))


def send_calendar_links(to_email, calendar_name, share_url, manager_url, admin_url):
    """Send the calendar access links to the owner's email address.

    Returns True on success, False on failure (logs the error).
    """
    if not is_email_configured():
        logger.warning("email.skip: SMTP not configured, cannot send calendar links")
        return False

    cfg = current_app.config
    from_name = cfg['SMTP_FROM_NAME']
    from_email = cfg['SMTP_FROM_EMAIL']

    subject = f"Your calendar links — {calendar_name}"

    # ── Plain-text body ──
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

    # ── HTML body ──
    html_body = f"""\
<html>
<body style="font-family:Inter,system-ui,sans-serif;background:#111827;color:#f8fafc;padding:24px;">
  <div style="max-width:600px;margin:0 auto;background:#1e293b;border-radius:12px;padding:24px;">
    <h1 style="color:#16a34a;margin-top:0;">📅 {calendar_name}</h1>
    <p>Your calendar has been created! Bookmark these links — they are the only way to access your calendar.</p>

    <h3 style="color:#cbd5e1;">📅 View (read-only, share this)</h3>
    <p><a href="{share_url}" style="color:#16a34a;">{share_url}</a></p>

    <h3 style="color:#cbd5e1;">📝 Manager (can create events)</h3>
    <p><a href="{manager_url}" style="color:#f59e0b;">{manager_url}</a></p>

    <h3 style="color:#cbd5e1;">🔑 Admin (full control)</h3>
    <p><a href="{admin_url}" style="color:#dc2626;">{admin_url}</a></p>

    <hr style="border:none;border-top:1px solid #334155;margin:24px 0;">
    <p style="color:#94a3b8;font-size:0.85rem;">
      Keep the admin link private! Anyone with it has full control over your calendar.
    </p>
  </div>
</body>
</html>"""

    msg = MIMEMultipart('alternative')
    msg['From'] = f"{from_name} <{from_email}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        host = cfg['SMTP_HOST']
        port = cfg['SMTP_PORT']
        use_tls = cfg['SMTP_USE_TLS']
        user = cfg['SMTP_USER']
        password = cfg['SMTP_PASSWORD']

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

        logger.info("email.sent", extra={"to": to_email, "calendar": calendar_name})
        return True

    except Exception as exc:
        logger.error("email.send_failed", extra={"to": to_email, "error": str(exc)})
        return False


def send_recovery_email(to_email, calendars, base_url):
    """Send a recovery email listing all calendars linked to this email.

    Args:
        to_email: The recipient email address.
        calendars: List of Calendar model instances owned by this email.
        base_url: The application base URL (e.g. http://localhost:5000).

    Returns True on success, False on failure.
    """
    if not is_email_configured():
        logger.warning("email.skip: SMTP not configured, cannot send recovery email")
        return False

    cfg = current_app.config
    from_name = cfg['SMTP_FROM_NAME']
    from_email = cfg['SMTP_FROM_EMAIL']

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

    # ── HTML body ──
    cal_rows = ""
    for cal in calendars:
        admin_url = f"{base_url}/cal/{cal.share_token}/admin/{cal.admin_token}"
        cal_rows += f"""
    <div style="background:#111827;border-radius:8px;padding:12px 16px;margin-bottom:8px;">
      <strong style="color:#f8fafc;">{cal.name}</strong>
      <br><a href="{admin_url}" style="color:#16a34a;font-size:0.9rem;">{admin_url}</a>
    </div>"""

    html_body = f"""\
<html>
<body style="font-family:Inter,system-ui,sans-serif;background:#111827;color:#f8fafc;padding:24px;">
  <div style="max-width:600px;margin:0 auto;background:#1e293b;border-radius:12px;padding:24px;">
    <h1 style="color:#16a34a;margin-top:0;">🔑 Calendar Recovery</h1>
    <p>Here are all calendars linked to <strong>{to_email}</strong>:</p>
    {cal_rows}
    <hr style="border:none;border-top:1px solid #334155;margin:24px 0;">
    <p style="color:#94a3b8;font-size:0.85rem;">
      Keep these links private! Anyone with an admin link has full control.
    </p>
  </div>
</body>
</html>"""

    msg = MIMEMultipart('alternative')
    msg['From'] = f"{from_name} <{from_email}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        host = cfg['SMTP_HOST']
        port = cfg['SMTP_PORT']
        use_tls = cfg['SMTP_USE_TLS']
        user = cfg['SMTP_USER']
        password = cfg['SMTP_PASSWORD']

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

        logger.info("email.recovery_sent", extra={"to": to_email, "count": len(calendars)})
        return True

    except Exception as exc:
        logger.error("email.recovery_failed", extra={"to": to_email, "error": str(exc)})
        return False


def send_regenerated_tokens_email(to_email, calendar_name, share_url, manager_url, admin_url):
    """Send an email with the new tokens after a token regeneration.

    Returns True on success, False on failure (logs the error).
    """
    if not is_email_configured():
        logger.warning("email.skip: SMTP not configured, cannot send regenerated tokens")
        return False

    cfg = current_app.config
    from_name = cfg['SMTP_FROM_NAME']
    from_email = cfg['SMTP_FROM_EMAIL']

    subject = f"⚠️ New access links — {calendar_name}"

    # ── Plain-text body ──
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

    # ── HTML body ──
    html_body = f"""\
<html>
<body style="font-family:Inter,system-ui,sans-serif;background:#111827;color:#f8fafc;padding:24px;">
  <div style="max-width:600px;margin:0 auto;background:#1e293b;border-radius:12px;padding:24px;">
    <h1 style="color:#dc2626;margin-top:0;">⚠️ Tokens Regenerated</h1>
    <p>All access tokens for <strong>{calendar_name}</strong> have been regenerated.
       All previous links are now <strong>invalid</strong>.</p>

    <h3 style="color:#cbd5e1;">📅 View (read-only)</h3>
    <p><a href="{share_url}" style="color:#16a34a;">{share_url}</a></p>

    <h3 style="color:#cbd5e1;">📝 Manager</h3>
    <p><a href="{manager_url}" style="color:#f59e0b;">{manager_url}</a></p>

    <h3 style="color:#cbd5e1;">🔑 Admin (full control)</h3>
    <p><a href="{admin_url}" style="color:#dc2626;">{admin_url}</a></p>

    <hr style="border:none;border-top:1px solid #334155;margin:24px 0;">
    <p style="color:#94a3b8;font-size:0.85rem;">
      If you did not request this change, someone with admin access regenerated the tokens.
      Bookmark the new admin link above to retain access.
    </p>
  </div>
</body>
</html>"""

    msg = MIMEMultipart('alternative')
    msg['From'] = f"{from_name} <{from_email}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        host = cfg['SMTP_HOST']
        port = cfg['SMTP_PORT']
        use_tls = cfg['SMTP_USE_TLS']
        user = cfg['SMTP_USER']
        password = cfg['SMTP_PASSWORD']

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

        logger.info("email.tokens_regenerated_sent", extra={
            "to": to_email, "calendar": calendar_name
        })
        return True

    except Exception as exc:
        logger.error("email.tokens_regenerated_failed", extra={
            "to": to_email, "error": str(exc)
        })
        return False
