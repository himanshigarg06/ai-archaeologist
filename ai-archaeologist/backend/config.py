"""
config.py — Application Configuration
======================================
Purpose:
    Loads all environment variables from .env and stores them as
    Python attributes. Every configurable value in the application
    lives here — no magic numbers scattered across files.

How it works:
    - load_dotenv() reads the .env file and puts its values into
      os.environ (the system's environment variable dictionary).
    - We then read those values using os.getenv().
    - Other files import Config and use Config.GITHUB_TOKEN, etc.

Student note:
    This is a simple class-based config pattern — just a container
    for settings. No complicated design pattern needed for Phase 1.
"""

import os
from dotenv import load_dotenv

# Absolute path to the project root (the ai-archaeologist/ folder).
# __file__ is this config.py file → its parent is backend/ → parent of that is project root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load variables from .env file into the environment.
# This must happen before any os.getenv() calls.
load_dotenv()


class Config:
    # ------------------------------------------------------------------
    # GitHub API settings
    # ------------------------------------------------------------------

    # Your GitHub Personal Access Token — never hardcoded, always from .env
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

    # Base URL for all GitHub REST API calls
    GITHUB_API_BASE_URL = "https://api.github.com"

    # How long (in seconds) to wait for GitHub to respond before giving up
    # Prevents the app from hanging forever if GitHub is slow
    GITHUB_REQUEST_TIMEOUT = 15

    # Maximum number of pages to fetch per paginated endpoint.
    # GitHub returns up to 100 items per page.
    # So 50 pages * 100 items = up to 5,000 commits/issues/PRs per repo.
    # Reduce this if you're testing with large repos to avoid long waits.
    MAX_PAGES_PER_REQUEST = 50

    # Items per page (GitHub's max is 100)
    ITEMS_PER_PAGE = 100

    # ------------------------------------------------------------------
    # Database settings
    # ------------------------------------------------------------------

    # Where the SQLite database file will be created.
    # We use an absolute path so it always resolves correctly regardless
    # of which directory you run the app from.
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(PROJECT_ROOT, 'data', 'archaeologist.db')}"
    )

    # SQLAlchemy setting: disables a feature we don't need.
    # If True, it would fire an event every time the database is modified —
    # unnecessary overhead for Phase 1.
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ------------------------------------------------------------------
    # Flask settings
    # ------------------------------------------------------------------

    # Secret key is required by Flask internally (e.g., for sessions).
    # We're not using sessions in Phase 1, but Flask requires this to exist.
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    # Debug mode: shows detailed errors in the browser during development.
    # In production this MUST be False — it exposes internals.
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"

    # ------------------------------------------------------------------
    # Data storage settings
    # ------------------------------------------------------------------

    # Folder where raw JSON API responses are saved for debugging
    RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")

    # Whether to save raw API responses to disk (useful for debugging)
    SAVE_RAW_RESPONSES = True
