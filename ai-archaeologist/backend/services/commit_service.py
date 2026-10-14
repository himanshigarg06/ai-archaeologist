"""Fetch and persist repository commit history."""

import logging

from backend.models import db
from backend.models.commit import Commit
from backend.services.github_service import GitHubService

logger = logging.getLogger(__name__)


class CommitService:
    """Collect GitHub commits and save them without creating duplicates."""

    MAX_DETAIL_REQUESTS = 20

    def __init__(self, github_service=None):
        self.github = github_service or GitHubService()

    def collect_commits(self, repository):
        """Save commit summaries and selectively enrich commit statistics."""

        result = self.github.get_commits(
            repository.owner,
            repository.name,
        )

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Could not fetch commits."),
            }

        # Handle the response structure returned by GitHubService.
        payload = result.get("data", [])
        warning = None

        if isinstance(payload, dict):
            commits = payload.get("data", [])
            warning = payload.get("warning")
        elif isinstance(payload, list):
            commits = payload
        else:
            commits = []

        if not isinstance(commits, list):
            return {
                "success": False,
                "error": "GitHub returned an invalid commit list.",
            }

        saved = 0
        updated = 0
        details_enriched = 0
        skipped = 0

        try:
            for item in commits:
                if not isinstance(item, dict):
                    skipped += 1
                    continue

                sha = item.get("sha")
                if not sha:
                    skipped += 1
                    continue

                existing = Commit.query.filter_by(
                    repository_id=repository.id,
                    sha=sha,
                ).first()

                commit_data = item.get("commit") or {}
                author_data = commit_data.get("author") or {}
                committer_data = commit_data.get("committer") or {}
                github_author = item.get("author") or {}

                if existing is None:
                    commit_record = Commit(
                        repository_id=repository.id,
                        sha=sha,
                    )
                    db.session.add(commit_record)
                    saved += 1
                else:
                    commit_record = existing
                    updated += 1

                # GitHub account details and Git commit author details
                # are different, so store them in their appropriate fields.
                commit_record.message = commit_data.get("message")
                commit_record.author_username = github_author.get("login")
                commit_record.author_name = (
                    author_data.get("name")
                    or committer_data.get("name")
                )
                commit_record.author_email = (
                    author_data.get("email")
                    or committer_data.get("email")
                )
                commit_record.committed_at = (
                    author_data.get("date")
                    or committer_data.get("date")
                )

                # Detailed requests are limited to avoid excessive API calls.
                needs_details = (
                    commit_record.additions is None
                    and commit_record.deletions is None
                    and commit_record.total_changes is None
                    and commit_record.files_changed is None
                )

                if (
                    needs_details
                    and details_enriched < self.MAX_DETAIL_REQUESTS
                ):
                    detail_result = self.github.get_commit_detail(
                        repository.owner,
                        repository.name,
                        sha,
                    )

                    if detail_result.get("success"):
                        detail = detail_result.get("data", {})
                        stats = detail.get("stats") or {}
                        files = detail.get("files") or []

                        commit_record.additions = stats.get("additions")
                        commit_record.deletions = stats.get("deletions")
                        commit_record.total_changes = stats.get("total")
                        commit_record.files_changed = len(files)
                        details_enriched += 1
                    else:
                        logger.warning(
                            "Could not enrich commit %s: %s",
                            sha[:8],
                            detail_result.get("error", "Unknown error"),
                        )

            db.session.commit()

        except Exception:
            db.session.rollback()
            logger.exception(
                "Failed to save commits for %s/%s",
                repository.owner,
                repository.name,
            )
            return {
                "success": False,
                "error": "Could not save commit history.",
            }

        return {
            "success": True,
            "data": {
                "fetched": len(commits),
                "newly_saved": saved,
                "already_existing": updated,
                "details_enriched": details_enriched,
                "skipped": skipped,
                "warning": warning,
            },
        }
