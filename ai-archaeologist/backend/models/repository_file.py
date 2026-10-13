from backend.models import db


class RepositoryFile(db.Model):
    __tablename__ = "repository_files"

    id = db.Column(db.Integer, primary_key=True)
    repository_id = db.Column(
        db.Integer,
        db.ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    path = db.Column(db.String(1024), nullable=False)
    name = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(30), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=True)
    sha = db.Column(db.String(40), nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "repository_id", "path",
            name="uq_repo_file_path",
        ),
    )

    repository = db.relationship("Repository", back_populates="files")

    def to_dict(self):
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "path": self.path,
            "name": self.name,
            "file_type": self.file_type,
            "size_bytes": self.size_bytes,
            "sha": self.sha,
        }
