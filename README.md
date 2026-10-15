# AdminBot

Self-hosted social media content automation, sold as source code.
Customers install it on their own servers.

> **Status: Task 01 — project foundation only.**
> This repository currently contains a minimal, runnable Django project:
> a landing page and a health-check endpoint. No business features yet.

## Prerequisites

- Python 3.10 or newer
- `pip` and `venv` (bundled with Python)
- Git

## Virtual environment setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

## Dependency installation

```bash
pip install -r requirements.txt
```

## Environment configuration

Copy the example environment file and adjust values for your machine:

```bash
cp .env.example .env
```

| Variable              | Purpose                                              | Default                 |
|-----------------------|------------------------------------------------------|-------------------------|
| `DJANGO_SECRET_KEY`   | Django cryptographic signing key (keep secret!)       | dev-only placeholder    |
| `DJANGO_DEBUG`        | Enable Django debug mode (local dev only)            | `True`                  |
| `DJANGO_ALLOWED_HOSTS`| Comma-separated list of allowed hosts                | `127.0.0.1,localhost`   |
| `DATABASE_URL`        | Database URL (`sqlite:///...` for local development) | `sqlite:///db.sqlite3`  |

Never commit a real `.env` file — it is git-ignored.

## Database migrations

```bash
python manage.py migrate
```

## Creating a Django superuser

```bash
python manage.py createsuperuser
```

## Running the development server

```bash
python manage.py runserver
```

Then open:

- Home page: <http://127.0.0.1:8000/>
- Health check: <http://127.0.0.1:8000/health/> (returns `{"status": "ok"}`)
- Admin: <http://127.0.0.1:8000/admin/>

## Running tests

```bash
python manage.py test
```

## Project structure

```
adminbot/
├── config/                 # Django project configuration (settings, URLs, WSGI/ASGI)
├── core/                   # Minimal app: home page, health check, tests
│   └── templates/core/     # Django templates (HTMX loaded on the home page)
├── manage.py
├── requirements.txt
├── .env.example            # Placeholders only — never real secrets
└── README.md
```

## Scope boundary

Task 01 intentionally stops at the foundation. The following are
**not** implemented yet and will arrive in later tasks: setup wizard,
business profiles, website analysis, AI content generation, scheduling,
social publishing, audience analysis, and deployment automation.
