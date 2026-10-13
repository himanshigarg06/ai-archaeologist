from backend.models import db


class PullRequest(db.Model):
    __tablename__ = "pull_requests"

    id = db.Column(db.Integer, primary_key=True)
    repository_id = db.Column(
        db.Integer,
        db.ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    pr_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.Text, nullable=True)
    state = db.Column(db.String(30), nullable=True)
    author_username = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.String(50), nullable=True)
    updated_at = db.Column(db.String(50), nullable=True)
    closed_at = db.Column(db.String(50), nullable=True)
    merged_at = db.Column(db.String(50), nullable=True)
    base_branch = db.Column(db.String(255), nullable=True)
    head_branch = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "repository_id", "pr_number",
            name="uq_pr_repo_number",
        ),
    )

    repository = db.relationship("Repository", back_populates="pull_requests")

    def to_dict(self):
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "pr_number": self.pr_number,
            "title": self.title,
            "state": self.state,
            "author_username": self.author_username,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "closed_at": self.closed_at,
            "merged_at": self.merged_at,
            "base_branch": self.base_branch,
            "head_branch": self.head_branch,
        }
