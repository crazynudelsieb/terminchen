# Contributing to terminchen

Thanks for your interest in contributing! This document explains how to get involved.

## Getting Started

1. **Fork** this repository
2. **Clone** your fork locally
3. **Set up** the development environment:

```bash
cp .env.example .env
# Edit .env with your local settings
docker compose -f docker-compose.local.yml up --build
```

4. Open `http://localhost:5000` and verify everything works.

## Development Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes — keep them focused and minimal.
3. Test locally with Docker Compose.
4. Commit with a clear message:
   ```bash
   git commit -m "Add: short description of change"
   ```
5. Push and open a **Pull Request** against `main`.

## Code Style

- **Python**: Follow existing conventions in the codebase (no type hints, Flask patterns).
- **Routes**: Admin/manager routes share logic via `_handle_*` helpers — don't duplicate.
- **Templates**: Jinja2 with `_` prefix for partials/components. Error pages use `errors/error.html` with `code`/`message` params.
- **CSS/JS**: Vanilla only — no frameworks or build tools.
- **Imports**: Keep at module level, no inline imports.
- **Forms**: Use WTForms validators (e.g. `_hex_color` for color fields). Add validation for new fields.
- **URL params**: Use `_safe_return_to()` and `_url_with_return_to()` for redirect URLs — never raw concatenation.
- **Constants**: Shared constants (like `VALID_RSVP_STATUSES`) live in their service module and are imported where needed.
- **Commits**: Use prefixes like `Add:`, `Fix:`, `Update:`, `Remove:`.

## What to Contribute

- Bug fixes and stability improvements
- Accessibility and mobile UX improvements
- Translations / i18n support
- Documentation improvements
- New calendar view modes or integrations

## What to Avoid

- Adding JavaScript frameworks or CSS preprocessors
- User account/authentication systems (this is intentionally account-free)
- Changes that require a paid API key
- Large refactors without prior discussion

## Reporting Bugs

Open an issue with:
- Steps to reproduce
- Expected vs. actual behavior
- Browser/OS if relevant
- Docker logs if applicable

## Suggesting Features

Open an issue tagged `enhancement` with:
- What problem it solves
- Proposed approach (brief)
- Whether you'd be willing to implement it

## License

By contributing, you agree that your contributions will be licensed under the
[CC BY-NC 4.0](LICENSE) license.
