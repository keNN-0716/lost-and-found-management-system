"""Test settings: reuse normal settings but use SQLite so tests can run
without a local PostgreSQL server (e.g. on CI or fresh dev machines).

Usage: uv run python manage.py test --settings=config.settings_test
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',  # noqa: F405
    }
}