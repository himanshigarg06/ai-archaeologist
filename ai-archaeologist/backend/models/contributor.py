from backend.models import db


class Contributor(db.Model):
    __tablename__ = "contributors"

    id = db.Column(db.Integer, primary_key=True)
    repository_id = db.Column(
        db.Integer,
        db.ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    username = db.Column(db.String(255), nullable=False)
    contributions = db.Column(db.Integer, default=0, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "repository_id", "username",
            name="uq_contributor_repo_username",
        ),
    )

    repository = db.relationship("Repository", back_populates="contributors")

    def to_dict(self):
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "username": self.username,
            "contributions": self.contributions,
        }
