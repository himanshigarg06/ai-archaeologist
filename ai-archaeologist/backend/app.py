"""
app.py — Flask Application Entry Point
=======================================
Purpose:
    This is the first file that runs when you start the backend.
    It is responsible for:
        1. Creating the Flask application object
        2. Configuring the database connection
        3. Creating all database tables (if they don't exist yet)
        4. Registering the API routes (blueprints)
        5. Starting the development server

How Flask apps work (for students):
    Flask uses an "application factory" concept — we create the app
    inside a function (create_app) rather than at the module level.
    This makes it easier to test and configure.

    A "Blueprint" is Flask's way of splitting routes across multiple
    files. We register our repository routes blueprint here.

Connection to other files:
    - Imports Config from config.py for all settings
    - Imports db from models/__init__.py (the SQLAlchemy instance)
    - Imports repository_routes blueprint from routes/
    - All models are imported in models/__init__.py so that
      SQLAlchemy knows about them when creating tables
"""

import logging
import os
import sys

from flask import Flask

# Add the project root to the Python path so imports work correctly
# when running: python backend/app.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import Config
from backend.models import db
from backend.routes.repository_routes import repository_bp

# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------
# basicConfig sets the format for all log messages in the application.
# We log to the console (stdout) during development.
# Format: timestamp | level | message
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def create_app():
    """
    Create and configure the Flask application.

    Returns:
        Flask: The configured Flask application object.

    Student note:
        Using a factory function (instead of a global app object) makes
        the app easier to test — tests can call create_app() to get a
        fresh instance with test settings.
    """
    app = Flask(__name__)

    # ----------------------------------------------------------------
    # Load configuration
    # ----------------------------------------------------------------
    # Tell Flask to use our Config class for all settings.
    # Flask reads DATABASE_URL as SQLALCHEMY_DATABASE_URI.
    app.config["SQLALCHEMY_DATABASE_URI"] = Config.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = Config.SQLALCHEMY_TRACK_MODIFICATIONS
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["DEBUG"] = Config.DEBUG

    # ----------------------------------------------------------------
    # Validate critical configuration
    # ----------------------------------------------------------------
    if not Config.GITHUB_TOKEN:
        logger.error(
            "GITHUB_TOKEN is not set. Please add it to your .env file. "
            "Without it, GitHub API calls will fail or be severely rate-limited."
        )
    else:
        logger.info("GitHub token loaded successfully.")

    # ----------------------------------------------------------------
    # Initialize the database
    # ----------------------------------------------------------------
    # db.init_app() connects our SQLAlchemy instance to this Flask app.
    # This must happen before we try to create tables or run queries.
    db.init_app(app)

    # Ensure the data/ directories exist (SQLite needs its parent folder to exist)
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(Config.RAW_DATA_DIR, exist_ok=True)

    # Create all database tables defined in our models.
    # with app.app_context() is required because SQLAlchemy needs to
    # know which Flask app it belongs to.
    with app.app_context():
        db.create_all()
        logger.info("Database tables created (or already exist).")

    # ----------------------------------------------------------------
    # Register blueprints (routes)
    # ----------------------------------------------------------------
    # A blueprint groups related routes together.
    # url_prefix means all routes in repository_bp start with /api/repositories
    app.register_blueprint(repository_bp, url_prefix="/api/repositories")
    logger.info("Repository routes registered at /api/repositories")

    # ----------------------------------------------------------------
    # Root health-check endpoint
    # ----------------------------------------------------------------
    @app.route("/")
    def health_check():
        """Simple health check to confirm the server is running."""
        return {
            "status": "ok",
            "message": "AI Archaeologist API is running.",
            "version": "1.0.0-phase1"
        }

    logger.info("Flask application created successfully.")
    return app


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
# This block only runs when you execute: python backend/app.py
# It does NOT run when another file imports this module.
if __name__ == "__main__":
    app = create_app()
    logger.info("Starting AI Archaeologist backend on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG)
