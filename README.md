# AdminBot

Self-hosted social media content automation, sold as source code.
Customers install it on their own servers.

> **Status: Task 02 — application foundation and configuration.**
> This repository currently contains a minimal, runnable Django project:
> a landing page, a health-check endpoint, a staff-only system-status page,
> and a placeholder for the future setup wizard. No business features yet.

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
- System status: <http://127.0.0.1:8000/system-status/> (staff users only; shows application/database/debug state, returns 503 if the database is unreachable)
- Business profile: <http://127.0.0.1:8000/business-profile/> (staff users only; create and edit the business profile and brand settings)
- Website analysis: <http://127.0.0.1:8000/website-analysis/> (staff users only; analyze a public website homepage)
- Setup wizard (placeholder): <http://127.0.0.1:8000/setup/>
- Admin: <http://127.0.0.1:8000/admin/>

## Running tests

```bash
python manage.py test
```

## Project structure

```
adminbot/
├── config/                 # Django project configuration (settings, URLs, WSGI/ASGI)
├── core/                   # Home page, health check, staff-only system-status page, tests
│   └── templates/core/     # Django templates (HTMX loaded on the home page)
├── setup_wizard/           # Placeholder foundation for the future web-based setup wizard
│   └── templates/setup_wizard/
├── business_profile/       # Single business profile: model, staff-only edit form, tests
│   ├── migrations/         # 0001_initial: BusinessProfile table
│   └── templates/business_profile/
├── website_analysis/       # Staff-only website analysis: safe fetch, parsing, reports
│   ├── migrations/         # 0001_initial: WebsiteAnalysis table
│   └── templates/website_analysis/
├── manage.py
├── requirements.txt
├── .env.example            # Placeholders only — never real secrets
└── README.md
```

### Apps

- **core**: landing page (`/`), health-check endpoint (`/health/`), and the
  staff-only system-status page (`/system-status/`).
- **setup_wizard**: placeholder foundation for the future installer.
  The actual setup wizard is **not implemented yet** — `/setup/` renders a
  static placeholder page and performs no configuration changes.
- **business_profile**: the single business profile with editable brand
  settings (`/business-profile/`, staff users only). The first visit shows an
  empty form to create the profile; later visits edit the existing one.

### Business profile

- **Single-business limitation**: the current version supports exactly one
  business profile per installation. The model enforces this by pinning the
  profile to a single database row; saving again updates that row instead of
  creating a new one.
- **Creating the initial profile**: log in as a staff user (e.g. via
  `python manage.py createsuperuser`), open `/business-profile/`, fill in
  the form, and save. No sample or seed data is created automatically.
- **Brand slogan toggle**: the `brand_slogan` text and the `use_brand_slogan`
  toggle are independent. Disabling the toggle does not delete the saved
  slogan text — it only signals that future content generation should omit
  the slogan. Editing or clearing the slogan never affects other fields.

### Website analysis

- **Purpose**: the `website_analysis` app fetches a public website homepage
  and extracts basic metadata for staff review. This is the first small
  increment — it does not crawl the full website, render JavaScript, or
  generate any content.
- **How to run an analysis**: log in as a staff user, open
  `/website-analysis/`, and submit a URL (the form is pre-filled with the
  business website from the business profile when one is configured).
  Recent reports and their status are listed on the same page; each
  completed report has a detail view with the extracted data.
- **Extracted data**: final URL (after validated redirects), HTTP status,
  HTML title, meta description, canonical URL, page language, headings
  (bounded), and same-site internal links with anchor text.
- **Heuristic link classification**: discovered links are classified from
  URL paths and anchor text only, into `likely_product`, `likely_service`,
  `likely_article`, `likely_about`, or `other`. These are guesses, not
  confirmed labels, and may be wrong. Only links on the exact same hostname
  are treated as internal; external links are ignored.
- **Network and security limitations**:
  - Only HTTP/HTTPS URLs without embedded credentials are accepted.
  - Every hostname is resolved and **all** resolved IPs must be globally
    routable (loopback, private, link-local, multicast, reserved, and
    unspecified addresses are rejected), re-checked on every redirect hop
    (max 5 redirects).
  - Short timeouts (5s connect / 15s read), 2 MiB response cap, HTML-only
    responses, no cookies or credentials are ever sent.
  - Residual DNS-rebinding risk: validation resolves DNS, but the HTTP
    client resolves again when connecting, so a hostile DNS could in theory
    return different addresses between the check and the request. Fully
    preventing this needs socket-level IP pinning and is out of scope;
    the per-hop validation still blocks the common cases.
  - Analysis runs synchronously in the request (no background workers yet).


## Scope boundary

Task 01 intentionally stops at the foundation. The following are
**not** implemented yet and will arrive in later tasks: setup wizard,
business profiles, website analysis, AI content generation, scheduling,
social publishing, audience analysis, and deployment automation.
