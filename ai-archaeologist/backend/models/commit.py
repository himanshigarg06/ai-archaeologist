"""
models/commit.py — Commit Database Model
=========================================
Purpose:
    Defines the 'commits' table in SQLite.
    Each row represents one Git commit from the repository's history.

Idempotency:
    The combination of (repository_id, sha) is unique.
    If the same commit is encountered again, we skip inserting it.
    Commits don't change once made, so no update is needed.

Student note — why store commits?
    The commit timeline is the most important data for software archaeology.
    Future phases will use it to:
        - Draw activity graphs (when was the project active?)
        - Detect periods of inactivity (when did development slow?)
        - Identify the last commit before abandonment
        - Correlate contributor activity over time
"""

from backend.models import db


class Commit(db.Model):
    """
    Represents a single Git commit in a repository.

    Table name: commits
    Primary key: id (auto-incrementing integer)
    Unique: (repository_id, sha)
    """

    __tablename__ = "commits"

    id = db.Column(db.Integer, primary_key=True)

    # Foreign key — links this commit to its repository
    # ondelete="CASCADE" means if the parent repo row is deleted,
    # all its commits are automatically deleted too
    repository_id = db.Column(
        db.Integer,
        db.ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False
    )

    # ------------------------------------------------------------------
    # Commit identity
    # ------------------------------------------------------------------

    # The full 40-character commit SHA (e.g. "a1b2c3d4...")
    sha = db.Column(db.String(40), nullable=False)

    # ------------------------------------------------------------------
    # Commit content
    # ------------------------------------------------------------------

    # The commit message (can be long, use Text)
    message = db.Column(db.Text, nullable=True)

    # ------------------------------------------------------------------
    # Author information
    # ------------------------------------------------------------------
    # GitHub distinguishes between:
    #   - "author" (who wrote the code)
    #   - "committer" (who committed it — can be different, e.g. GitHub merge)
    # We store the author. Both username and name may be missing.

    # GitHub username (e.g. "torvalds") — may be None for deleted accounts
    author_username = db.Column(db.String(255), nullable=True)

    # Display name from the Git config (e.g. "Linus Torvalds")
    author_name     = db.Column(db.String(255), nullable=True)

    # Author email from the Git config
    author_email    = db.Column(db.String(255), nullable=True)

    # ------------------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------------------

    # When the commit was authored (ISO 8601 string from GitHub)
    committed_at = db.Column(db.String(50), nullable=True)

    # ------------------------------------------------------------------
    # Change statistics (from the detailed commit endpoint)
    # These may be None if we didn't fetch commit details
    # ------------------------------------------------------------------

    additions      = db.Column(db.Integer, nullable=True)  # lines added
    deletions      = db.Column(db.Integer, nullable=True)  # lines removed
    total_changes  = db.Column(db.Integer, nullable=True)  # additions + deletions
    files_changed  = db.Column(db.Integer, nullable=True)  # number of files touched

    # ------------------------------------------------------------------
    # Unique constraint
    # ------------------------------------------------------------------
    __table_args__ = (
        db.UniqueConstraint("repository_id", "sha", name="uq_commit_repo_sha"),
    )

    # Relationship back to the parent repository
    repository = db.relationship("Repository", back_populates="commits")

    def __repr__(self):
        return f"<Commit {self.sha[:8]}... in repo {self.repository_id}>"

    def to_dict(self):
        return {
            "id":             self.id,
            "sha":            self.sha,
            "message":        self.message,
            "author_username":self.author_username,
            "author_name":    self.author_name,
            "author_email":   self.author_email,
            "committed_at":   self.committed_at,
            "additions":      self.additions,
            "deletions":      self.deletions,
            "total_changes":  self.total_changes,
            "files_changed":  self.files_changed,
        }
