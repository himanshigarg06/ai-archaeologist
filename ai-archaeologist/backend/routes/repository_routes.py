
import logging

from flask import Blueprint, jsonify, request

from backend.services.repository_service import RepositoryService
from backend.models.repository import Repository
from backend.models.commit import Commit

logger = logging.getLogger(__name__)
repository_bp = Blueprint("repository", __name__)


@repository_bp.route("/analyze", methods=["POST"])
def analyze_repository():
    body = request.get_json(silent=True) or {}
    url = body.get("url")

    result = RepositoryService().analyze_repository(url)
    status_code = result.pop("status_code", 200)

    return jsonify(result), status_code


@repository_bp.route("/<owner>/<repo>", methods=["GET"])
def get_repository(owner, repo):
    repository = Repository.query.filter_by(
        owner=owner,
        name=repo,
    ).first()

    if repository is None:
        return jsonify({
            "success": False,
            "error": "Repository not found. Analyze it first.",
        }), 404

    return jsonify({
        "success": True,
        "data": repository.to_dict(),
    }), 200



@repository_bp.route("/<owner>/<repo>/commits", methods=["GET"])
def get_commits(owner, repo):
    repository = Repository.query.filter_by(
        owner=owner,
        name=repo,
    ).first()

    if repository is None:
        return jsonify({
            "success": False,
            "error": "Repository not found. Analyze it first.",
        }), 404

    commits = (
        Commit.query
        .filter_by(repository_id=repository.id)
        .order_by(Commit.committed_at.desc())
        .all()
    )

    return jsonify({
        "success": True,
        "count": len(commits),
        "data": [commit.to_dict() for commit in commits],
    }), 200



@repository_bp.route("/<owner>/<repo>/contributors", methods=["GET"])
def get_contributors(owner, repo):
    return jsonify({
        "success": False,
        "message": "Contributor storage is not implemented yet.",
    }), 501


@repository_bp.route("/<owner>/<repo>/files", methods=["GET"])
def get_files(owner, repo):
    return jsonify({
        "success": False,
        "message": "File storage is not implemented yet.",
    }), 501


@repository_bp.route("/<owner>/<repo>/issues", methods=["GET"])
def get_issues(owner, repo):
    return jsonify({
        "success": False,
        "message": "Issue storage is not implemented yet.",
    }), 501


@repository_bp.route("/<owner>/<repo>/pull-requests", methods=["GET"])
def get_pull_requests(owner, repo):
    return jsonify({
        "success": False,
        "message": "Pull request storage is not implemented yet.",
    }), 501
