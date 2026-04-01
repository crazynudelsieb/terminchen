# terminchen

Lightweight, account-free shared calendar for friend groups, clubs, and communities.

## Features

- **No accounts needed** — share calendars via token-based URLs (3-tier: share / manager / admin)
- **RSVP** — in / maybe / out with member avatars (DiceBear random avatars or custom uploads)
- **iCal feed** — subscribe from Outlook, Google Calendar, Apple Calendar
- **Embeddable** — drop an iframe, use the JSON API, or embed a countdown widget
- **Dark-mode-first** — mobile-first, dark-only UI with PWA install support
- **Month / Week / Agenda views** — switchable calendar views with navigation
- **Birthdays** — member birthdays shown across all views and in the iCal feed
- **Public holidays** — local holiday overlay auto-detected from your timezone
- **Weather forecast** — 14-day forecast overlay via Open-Meteo (no API key needed)
- **Tags & filtering** — color-coded event tags with calendar-wide filter
- **QR code sharing** — instant QR code for any calendar or event link
- **Date & time formats** — configurable EU (dd.mm.yyyy) or US (mm/dd/yyyy), 12h or 24h
- **Email notifications** — optional SMTP for calendar link delivery and recovery
- **Token regeneration** — compromise recovery: regenerate all tokens at once
- **Audit log** — track event and RSVP changes in the admin dashboard
- **Bulk RSVP** — set all members to "in" with one click (admin only)

## Quick Start

### Docker (recommended)

```bash
# 1. Clone and configure
git clone https://github.com/crazynudelsieb/terminchen.git
cd terminchen
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY and POSTGRES_PASSWORD

# 2. Start
docker compose up -d --build

# 3. Open http://localhost:5000
```

### Pre-built image (ghcr.io)

```bash
# Pull the latest image
docker pull ghcr.io/crazynudelsieb/terminchen:main

# Or use a tagged release
docker pull ghcr.io/crazynudelsieb/terminchen:v1.0.0
```

Available for `linux/amd64` and `linux/arm64`.

### Local development (without Docker)

```bash
python -m venv venv
source venv/bin/activate    # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env        # configure DATABASE_URL for your local PostgreSQL
python app.py
```

## Production Deployment

```bash
docker compose up -d --build
```

Put it behind a reverse proxy (Traefik / Nginx / Caddy) for HTTPS, then set in `.env`:

```
SECURE_COOKIES=true
BASE_URL=https://your-domain.com
```

## Configuration

All configuration is via environment variables. See [`.env.example`](.env.example) for the full list with descriptions.

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Flask session secret | *(must set)* |
| `DATABASE_URL` | PostgreSQL connection string | *(must set)* |
| `BASE_URL` | Public URL of the app | `http://localhost:5000` |
| `DEFAULT_TIMEZONE` | Default timezone for new calendars | `Europe/Vienna` |
| `DEFAULT_VIEW` | Default calendar view (`month`/`week`/`agenda`) | `month` |
| `MAX_UPLOAD_SIZE_MB` | Max avatar upload size | `2` |
| `SMTP_HOST` | SMTP server (leave empty to disable email) | *(empty)* |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username | *(empty)* |
| `SMTP_PASSWORD` | SMTP password | *(empty)* |
| `SECURE_COOKIES` | Enable secure cookies (set `true` behind HTTPS) | `false` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of CORS origins for `/api/*` | *(empty)* |
| `EMBED_ALLOWED_ORIGINS` | Comma-separated list of allowed iframe origins | *(empty)* |

## Project Structure

```
app/
├── __init__.py          # Flask factory
├── config.py            # Environment configuration
├── database.py          # SQLAlchemy setup & lightweight migrations
├── models.py            # SQLAlchemy models (Calendar, Event, Member, RSVP, EventTag, AuditLog)
├── routes.py            # All route handlers (shared helpers DRY admin/manager logic)
├── forms.py             # WTForms definitions
├── utils.py             # Date/time formatting, sanitization, timezone helpers
├── security.py          # CSP, HSTS, and security headers middleware
├── error_handlers.py    # Custom 403/404/500 error pages
├── services/            # Business logic layer
│   ├── calendar_service.py
│   ├── event_service.py
│   ├── rsvp_service.py
│   ├── member_service.py
│   ├── tag_service.py
│   ├── feed_service.py  # iCal (.ics) feed generation
│   ├── email_service.py # SMTP email delivery
│   ├── audit_service.py
│   ├── holiday_service.py
│   ├── weather_service.py
│   └── upload_service.py
├── templates/           # Jinja2 templates
└── static/              # CSS, JS, icons, PWA assets
```

## Key URLs

| URL | Description |
|---|---|
| `/` | Create a new calendar |
| `/cal/<share_token>` | View calendar (read-only) |
| `/cal/<share_token>/manage/<manager_token>` | Manager access (create/edit events & members) |
| `/cal/<share_token>/admin/<admin_token>` | Admin dashboard (full control) |
| `/cal/<share_token>/feed.ics` | iCal subscription feed |
| `/event/<event_token>` | Shareable event detail page |
| `/cal/<share_token>/embed` | Embeddable calendar view |
| `/recover` | Recover calendar links by email |

### Countdown Widget

Embed a live countdown to the next event on any page:

```html
<div id="terminchen-countdown" data-token="YOUR_SHARE_TOKEN" data-base="https://your-domain.com"></div>
<script src="https://your-domain.com/static/js/countdown.js"></script>
```

## Tech Stack

- **Backend:** Python 3.14, Flask, SQLAlchemy, Gunicorn
- **Database:** PostgreSQL 17
- **Frontend:** Vanilla JS + CSS (no build step)
- **Container:** Multi-stage Docker build, Docker Compose
- **CI:** GitHub Actions (multi-arch build), Dependabot

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to participate.

## License

This project is licensed under [CC BY-NC 4.0](LICENSE) — free to use and adapt for non-commercial purposes with attribution.
