# SSL Certificate Tracker - Engineering & Architecture Rules

## Stack
- Python 3.11+, Django 5.x, SQLite
- Standard library / Django native tools (No unnecessary external packages)
- `requirements.txt` pins Django (e.g. `Django>=5.0,<6`); README setup steps rely on it.

## Scope (keep it simple)
- In scope: `Certificate` model, Django admin CRUD, one public list page, status tests, README.
- Out of scope, do NOT add: authentication/login, Celery, live TLS scanning, email/notifications, REST API, wildcard-domain regex validation.
- The list page is intentionally public (the assignment expects no user login). State this as a deliberate choice in README.

## Settings
- `USE_TZ = True`, `TIME_ZONE = 'Europe/Istanbul'`, `LANGUAGE_CODE = 'tr'`.
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` are read from environment variables (dev-safe defaults allowed, no real secret committed).
- `.gitignore` includes `db.sqlite3`, `.env`, `__pycache__/`, venv folders.

## Domain & Business Logic Rules
- Model: `Certificate` (domain_name, customer_name, expiration_date)
  - `expiration_date` is a `DateField` (calendar day in Europe/Istanbul), `db_index=True`.
  - `Meta.ordering = ['expiration_date']`; sorting happens in the DB, not in Python.
  - `unique_together = (domain_name, expiration_date)`. `domain_name` alone is NOT unique (renewals overlap with the old certificate).
- "Today" is ALWAYS `django.utils.timezone.localdate()`. Never `datetime.now()`, never naive datetimes, and never compare a `datetime` (`timezone.now()`) with the `DateField`.
- Remaining days = `(expiration_date - today).days` (negative once expired).
- Boundary: `expiration_date == today` means 0 days left; the certificate is valid until end of day and counts as "Yakında Dolacak".
- Status definitions (single threshold constant `EXPIRY_WARNING_DAYS = 30`; never hard-code 30 elsewhere):
  - "Süresi Dolmuş" (Expired): days_left < 0
  - "Yakında Dolacak" (Expiring Soon): 0 <= days_left <= EXPIRY_WARNING_DAYS
  - "Geçerli" (Valid): days_left > EXPIRY_WARNING_DAYS
- Single source of truth: the model methods `days_left(today=None)` and `status(today=None)` are the only place status logic lives. Admin and list template call them; no duplicate calculation. Status label strings are defined once as constants.
- `today=None` parameter: when `None`, use `timezone.localdate()`; otherwise use the passed `date`.

## Admin
- `list_display`: domain_name, customer_name, expiration_date, days left, status.
- `list_filter`: expiration_date (and/or status-based filter), `search_fields`: domain_name, customer_name.

## Testing Standards
- Do not mock the clock. Pass `today=` explicitly into the model methods; tests must never depend on the real date.
- Minimum 5 status tests; boundary set is mandatory: yesterday (-1), today (0), +29, +30, +31 days. Also cover far future and far past.
- Add one view test: list page ordering by `expiration_date` and displayed status text.
- Add one test for `unique_together` behaviour (same domain, different date allowed; same pair rejected).

## README
- Setup (venv, `pip install -r requirements.txt`, migrate, createsuperuser, runserver), how to run tests, status rules, and the "public list page is intentional" note.
