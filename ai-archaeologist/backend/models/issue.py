from backend.models import db


class Issue(db.Model):
    __tablename__ = "issues"

    id = db.Column(db.Integer, primary_key=True)
    repository_id = db.Column(
        db.Integer,
        db.ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    issue_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.Text, nullable=True)
    state = db.Column(db.String(30), nullable=True)
    author_username = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.String(50), nullable=True)
    updated_at = db.Column(db.String(50), nullable=True)
    closed_at = db.Column(db.String(50), nullable=True)
    comments = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.UniqueConstraint(
            "repository_id", "issue_number",
            name="uq_issue_repo_number",
        ),
    )

    repository = db.relationship("Repository", back_populates="issues")

    def to_dict(self):
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "issue_number": self.issue_number,
            "title": self.title,
            "state": self.state,
            "author_username": self.author_username,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "closed_at": self.closed_at,
            "comments": self.comments,
        }
