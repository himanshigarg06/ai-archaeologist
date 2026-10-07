"""
models/__init__.py — Shared Database Instance
==============================================
Purpose:
    Creates a single SQLAlchemy database object (db) that is shared
    across ALL model files.

Why this matters (student note):
    SQLAlchemy needs one central "db" object that all models use.
    If each model created its own db object, they wouldn't talk
    to the same database.

    By creating db here and importing it everywhere, we ensure
    all models belong to the same database instance.

    app.py then calls db.init_app(app) to connect this db object
    to the running Flask application.

Import pattern used elsewhere:
    from backend.models import db          ← to access the db object
    from backend.models.repository import Repository  ← to access models
"""

from flask_sqlalchemy import SQLAlchemy

# This is the single shared database instance used by all models.
# It is intentionally created here with no arguments —
# it gets connected to the Flask app later via db.init_app(app) in app.py.
db = SQLAlchemy()
