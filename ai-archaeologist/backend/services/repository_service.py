import json
import logging
from datetime import datetime, timezone

from backend.models import db
from backend.models.repository import Repository
from backend.services.github_service import GitHubService
from backend.utils.validators import validate_github_url
from backend.services.commit_service import CommitService

logger = logging.getLogger(__name__)


class RepositoryService:
    def __init__(self, github_service=None):
        self.github = github_service or GitHubService()

    def analyze_repository(self, url):
        # Validate the URL before calling GitHub.
        validation = validate_github_url(url)

        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"],
                "status_code": 400,
            }

        owner = validation["owner"]
        repo_name = validation["repo"]

        # Fetch repository information.
        result = self.github.get_repository(owner, repo_name)

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "GitHub request failed."),
                "details": result.get("details"),
                "status_code": 502,
            }

        metadata = result.get("data", {})

        # Fetch programming-language statistics.
        language_result = self.github.get_languages(owner, repo_name)

        if not language_result.get("success"):
            return {
                "success": False,
                "error": language_result.get("error", "Could not fetch languages."),
                "details": language_result.get("details"),
                "status_code": 502,
            }

        languages = language_result.get("data", {})
        now = datetime.now(timezone.utc)

        try:
            repository = Repository.query.filter_by(
                owner=owner,
                name=repo_name,
            ).first()

            if repository is None:
                repository = Repository(owner=owner, name=repo_name)
                db.session.add(repository)

            # Update only attributes that exist in your model.
            fields = {
                "full_name": metadata.get("full_name"),
                "description": metadata.get("description"),
                "url": metadata.get("url"),
                "default_branch": metadata.get("default_branch"),
                "language": metadata.get("language"),
                "languages_json": json.dumps(languages),
                "stars": metadata.get("stars", 0),
                "forks": metadata.get("forks", 0),
                "watchers": metadata.get("watchers", 0),
                "open_issues": metadata.get("open_issues", 0),
                "size_kb": metadata.get("size_kb", 0),
                "is_archived": metadata.get("is_archived", False),
                "is_fork": metadata.get("is_fork", False),
                "topics_json": json.dumps(metadata.get("topics", [])),
                "last_analyzed_at": now,
            }

            license_data = metadata.get("license")
            fields["license"] = (
                license_data.get("name")
                if isinstance(license_data, dict)
                else license_data
            )

            # Support whichever timestamp names the model defines.
            for candidates, value in [
                (("github_created_at", "created_at"), metadata.get("created_at")),
                (("github_updated_at", "updated_at"), metadata.get("updated_at")),
                (("github_pushed_at", "pushed_at"), metadata.get("pushed_at")),
            ]:
                for field in candidates:
                    if hasattr(repository, field):
                        fields[field] = value
                        break

            for field, value in fields.items():
                if hasattr(repository, field):
                    setattr(repository, field, value)

            db.session.commit()
            commit_result = CommitService(
            github_service=self.github
            ).collect_commits(repository)

            if not commit_result.get("success"):
            logger.warning(
            "Repository metadata saved, but commit collection failed: %s",
            commit_result.get("error"),
            )
            return {
                "success": True,
                "message": "Repository analyzed successfully.",
                "data": repository.to_dict(),
                "status_code": 200,
            }

        except Exception:
            db.session.rollback()
            logger.exception("Could not save repository %s/%s", owner, repo_name)

            return {
                "success": False,
                "error": "Could not save repository data.",
                "status_code": 500,
            }
