"""
models/repository.py — Repository Database Model
==================================================
Purpose:
    Defines the 'repositories' table in SQLite.
    Every other table (commits, issues, PRs, files, contributors) has
    a foreign key pointing back to a row in this table.

Think of it as the "parent" record — when you analyze a repo, one row
is created here first, and everything else links to it via repository_id.

SQLAlchemy basics (student note):
    - db.Model is the base class every model inherits from.
    - Each class attribute with db.Column(...) becomes a column in the table.
    - db.relationship(...) creates a Python-level link between models.
      It doesn't add a column — it lets you do repo.commits to get all
      commits for that repo as a Python list.

Idempotency:
    The combination of (owner, name) is marked unique with a constraint.
    If you analyze the same repo twice, we UPDATE the existing row instead
    of inserting a duplicate. This is handled in repository_service.py.
"""

from datetime import datetime, timezone
from backend.models import db


class Repository(db.Model):
    """
    Represents a GitHub repository.

    Table name: repositories
    Primary key: id (auto-incrementing integer)
    Unique constraint: (owner, name) — no two rows for the same repo
    """

    __tablename__ = "repositories"

    # Primary key — auto-increments for every new row
    id = db.Column(db.Integer, primary_key=True)

    # ------------------------------------------------------------------
    # Identity fields — used to uniquely identify the repo
    # ------------------------------------------------------------------

    # GitHub username or organisation name (e.g. "torvalds")
    owner = db.Column(db.String(255), nullable=False)

    # Repository name (e.g. "linux")
    name = db.Column(db.String(255), nullable=False)

    # "owner/name" — convenient for display (e.g. "torvalds/linux")
    full_name = db.Column(db.String(512), nullable=True)

    # ------------------------------------------------------------------
    # Metadata fields — all nullable because not every repo has every field
    # ------------------------------------------------------------------

    description    = db.Column(db.Text, nullable=True)
    url            = db.Column(db.String(512), nullable=True)
    default_branch = db.Column(db.String(255), nullable=True)
    language       = db.Column(db.String(100), nullable=True)   # primary language
    languages_json = db.Column(db.Text, nullable=True)          # all languages as JSON string
    stars          = db.Column(db.Integer, default=0)
    forks          = db.Column(db.Integer, default=0)
    watchers       = db.Column(db.Integer, default=0)
    open_issues    = db.Column(db.Integer, default=0)
    size_kb        = db.Column(db.Integer, default=0)
    license        = db.Column(db.String(255), nullable=True)
    topics_json    = db.Column(db.Text, nullable=True)          # topics list as JSON string
    is_archived    = db.Column(db.Boolean, default=False)
    is_fork        = db.Column(db.Boolean, default=False)

    # Timestamps from GitHub (stored as strings in ISO 8601 format)
    github_created_at = db.Column(db.String(50), nullable=True)
    github_updated_at = db.Column(db.String(50), nullable=True)
    github_pushed_at  = db.Column(db.String(50), nullable=True)

    # ------------------------------------------------------------------
    # Our own bookkeeping timestamps
    # ------------------------------------------------------------------

    # When we first analyzed this repo
    first_analyzed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # When we last ran analysis on this repo (updated on re-analysis)
    last_analyzed_at  = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # ------------------------------------------------------------------
    # Unique constraint — prevents duplicate rows for the same repo
    # ------------------------------------------------------------------
    __table_args__ = (
        db.UniqueConstraint("owner", "name", name="uq_repository_owner_name"),
    )

    # ------------------------------------------------------------------
    # Relationships — let us do repo.commits, repo.issues, etc.
    # cascade="all, delete-orphan" means if we delete the repo row,
    # all related commits/issues/etc. are also deleted automatically.
    # ------------------------------------------------------------------
    commits      = db.relationship("Commit",         back_populates="repository", cascade="all, delete-orphan")
    contributors = db.relationship("Contributor",    back_populates="repository", cascade="all, delete-orphan")
    issues       = db.relationship("Issue",          back_populates="repository", cascade="all, delete-orphan")
    pull_requests= db.relationship("PullRequest",    back_populates="repository", cascade="all, delete-orphan")
    files        = db.relationship("RepositoryFile", back_populates="repository", cascade="all, delete-orphan")

    def __repr__(self):
        """String representation — useful when debugging in the Python shell."""
        return f"<Repository {self.full_name}>"

    def to_dict(self):
        """
        Convert the model to a plain Python dictionary.

        Used when building the JSON API response.
        We never return the SQLAlchemy object directly to Flask routes.
        """
        import json
        return {
            "id":               self.id,
            "owner":            self.owner,
            "name":             self.name,
            "full_name":        self.full_name,
            "description":      self.description,
            "url":              self.url,
            "default_branch":   self.default_branch,
            "language":         self.language,
            "languages":        json.loads(self.languages_json) if self.languages_json else {},
            "stars":            self.stars,
            "forks":            self.forks,
            "watchers":         self.watchers,
            "open_issues":      self.open_issues,
            "size_kb":          self.size_kb,
            "license":          self.license,
            "topics":           json.loads(self.topics_json) if self.topics_json else [],
            "is_archived":      self.is_archived,
            "is_fork":          self.is_fork,
            "github_created_at":self.github_created_at,
            "github_updated_at":self.github_updated_at,
            "github_pushed_at": self.github_pushed_at,
            "first_analyzed_at":self.first_analyzed_at.isoformat() if self.first_analyzed_at else None,
            "last_analyzed_at": self.last_analyzed_at.isoformat() if self.last_analyzed_at else None,
        }
