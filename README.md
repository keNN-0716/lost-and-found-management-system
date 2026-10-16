# Lost and Found Management System

A Django-based lost and found management system with role-based access, item reporting, image uploads, search, and a claim/resolve workflow.

## Features

- **ID-number login** — users sign in with their college/school ID number (custom auth backend) instead of an email.
- **Role-based access**
  - *Normal users* — report lost/found items, browse lists, search, claim items, and track their own reports/claims from their home page.
  - *Management* — everything above, plus access to the management dashboard and the ability to resolve claimed items.
- **Lost & found item reporting** with optional image upload (server-side validated: JPEG/PNG/GIF/WebP, max 5 MB).
- **Search** across item name, description, and location.
- **Claim workflow** — items move through `Open ? Claimed ? Resolved`, with status badges shown in the UI.
- **Django admin** for managing users and items.

## Tech stack

- Python 3.12+ / Django 6
- PostgreSQL (SQLite for the test suite)
- [uv](https://docs.astral.sh/uv/) for dependency management

## Setup

1. **Clone and sync dependencies**

   ```powershell
   git clone <repo-url>
   cd lost-and-found-management-system
   uv sync
   ```

2. **Configure the environment**

   ```powershell
   Copy-Item .env.example .env
   ```

   Then edit `.env` and set your real `SECRET_KEY` and database credentials.

3. **Create the database and run migrations**

   ```powershell
   # In PostgreSQL: CREATE DATABASE lost_and_found;
   uv run python manage.py migrate
   ```

4. **Create an admin/management account**

   ```powershell
   uv run python manage.py createsuperuser
   ```

   Then set the user's `role` to `Management` (and an `id_number`) in the Django admin at `/admin/`.

5. **Run the development server**

   ```powershell
   uv run python manage.py runserver
   ```

## Tests

The test suite runs on SQLite (no PostgreSQL needed):

```powershell
uv run python manage.py test --settings=config.settings_test
```

## Project structure

```
config/                 # Django project settings, urls, wsgi/asgi
LostAndFound/           # Main app
  backends.py           # Custom ID-number authentication backend
  decorators.py         # management_required role decorator
  forms.py              # Login/signup forms + item ModelForms with image validation
  models.py             # CustomUser, LostItem, FoundItem, ItemStatus
  views.py              # All view logic (auth, items, search, claims)
LostAndFound/templates/ # HTML templates
static/                 # CSS and JavaScript
```

## Notes for existing databases

If you are upgrading an existing database, run `uv run python manage.py migrate` to add the new `status` / `reported_by` / `claimed_by` columns and the `FoundItem` table. Existing users with no `id_number` cannot log in until an admin assigns one via `/admin/`.