"""
tests/test_github_service.py — Tests for GitHub API Service
=============================================================
Purpose:
    Tests that GitHubService handles both success and error scenarios
    correctly — without making real GitHub API calls.

Why we use mocking:
    Making real API calls in tests is bad practice because:
        1. Tests become slow (each call takes ~0.5-2 seconds)
        2. Tests break if GitHub is down or rate-limited
        3. Tests consume your rate limit quota
        4. Tests are non-deterministic (results change over time)

    Instead, we use pytest-mock's mocker.patch() to replace the actual
    HTTP requests with fake responses we control. This way tests are:
        - Fast (no network)
        - Reliable (no external dependencies)
        - Repeatable (same result every time)

How mocker.patch works:
    mocker.patch("backend.services.github_service.requests.Session")
    This replaces requests.Session with a fake (MagicMock) for the
    duration of that test only. After the test, the real Session is restored.

How to run:
    pytest tests/test_github_service.py -v
"""

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.github_service import GitHubService
from backend.utils.github_helpers import (
    parse_next_page_url,
    is_rate_limited,
    make_error,
    make_success,
)


# ---------------------------------------------------------------------------
# Helper: build a fake requests.Response object
# ---------------------------------------------------------------------------

def make_mock_response(status_code: int, json_data=None, headers=None):
    """
    Creates a fake requests.Response-like object for testing.

    We use a simple class instead of MagicMock so that all attributes
    behave exactly as expected — MagicMock can sometimes return a new
    MagicMock() for attributes we haven't explicitly set, which can
    cause subtle failures.

    Args:
        status_code (int): HTTP status code to simulate.
        json_data:         Data that .json() should return.
        headers (dict):    Response headers to include.

    Returns:
        A simple object that behaves like a requests.Response.
    """
    class FakeResponse:
        pass

    resp = FakeResponse()
    resp.status_code = status_code
    resp.ok = (200 <= status_code < 300)
    resp.headers = headers or {}
    resp.text = str(json_data or "")
    _json_data = json_data if json_data is not None else {}
    resp.json = lambda: _json_data
    return resp


# ===========================================================================
# TESTS FOR github_helpers.py utilities
# ===========================================================================

class TestParseNextPageUrl:
    """Tests for the Link header pagination parser."""

    def test_finds_next_link(self):
        """Standard Link header with next and last links."""
        header = '<https://api.github.com/repos/owner/repo/commits?page=2>; rel="next", <https://api.github.com/repos/owner/repo/commits?page=5>; rel="last"'
        result = parse_next_page_url(header)
        assert result == "https://api.github.com/repos/owner/repo/commits?page=2"

    def test_no_next_link_returns_none(self):
        """On the last page, there is no rel='next' — should return None."""
        header = '<https://api.github.com/repos/owner/repo/commits?page=5>; rel="last"'
        result = parse_next_page_url(header)
        assert result is None

    def test_empty_header_returns_none(self):
        """Empty Link header means no more pages."""
        assert parse_next_page_url("") is None

    def test_none_header_returns_none(self):
        """Missing Link header (None) means no more pages."""
        assert parse_next_page_url(None) is None

    def test_only_next_link(self):
        """Link header with only a next link (no last link)."""
        header = '<https://api.github.com/repos/owner/repo/commits?page=2>; rel="next"'
        result = parse_next_page_url(header)
        assert result == "https://api.github.com/repos/owner/repo/commits?page=2"


class TestIsRateLimited:
    """Tests for rate limit detection."""

    def test_status_429_is_rate_limited(self):
        """HTTP 429 Too Many Requests always means rate limited."""
        resp = make_mock_response(429, {})
        assert is_rate_limited(resp) is True

    def test_status_403_with_zero_remaining_is_rate_limited(self):
        """HTTP 403 with X-RateLimit-Remaining: 0 means rate limited."""
        resp = make_mock_response(403, {}, headers={"X-RateLimit-Remaining": "0"})
        assert is_rate_limited(resp) is True

    def test_status_403_with_remaining_is_not_rate_limited(self):
        """HTTP 403 with remaining > 0 is a different kind of 403 (e.g. permissions)."""
        resp = make_mock_response(403, {}, headers={"X-RateLimit-Remaining": "100"})
        assert is_rate_limited(resp) is False

    def test_status_200_is_not_rate_limited(self):
        """Successful response is never rate limited."""
        resp = make_mock_response(200, {})
        assert is_rate_limited(resp) is False

    def test_status_404_is_not_rate_limited(self):
        """404 Not Found is not a rate limit error."""
        resp = make_mock_response(404, {})
        assert is_rate_limited(resp) is False


class TestMakeErrorAndSuccess:
    """Tests for the response builder helpers."""

    def test_make_error_has_required_keys(self):
        """make_error should always return success=False with error key."""
        result = make_error("Something failed", "Details here")
        assert result["success"] is False
        assert result["error"] == "Something failed"
        assert result["details"] == "Details here"

    def test_make_error_without_details(self):
        """details defaults to empty string if not provided."""
        result = make_error("Something failed")
        assert result["success"] is False
        assert "details" in result

    def test_make_success_merges_data(self):
        """make_success should add success=True and merge the data dict."""
        result = make_success({"owner": "django", "repo": "django"})
        assert result["success"] is True
        assert result["owner"] == "django"
        assert result["repo"] == "django"


# ===========================================================================
# TESTS FOR GitHubService
# ===========================================================================

class TestGitHubServiceCheckExists:
    """Tests for check_repository_exists()."""

    def test_repository_exists(self, mocker):
        """A 200 response means the repository exists."""
        mock_session = MagicMock()
        mock_session.get.return_value = make_mock_response(200, {"name": "django"})
        mocker.patch("backend.services.github_service.requests.Session", return_value=mock_session)

        service = GitHubService()
        result = service.check_repository_exists("django", "django")

        assert result["success"] is True
        assert result["exists"] is True

    def test_repository_not_found(self, mocker):
        """A 404 response means the repository does not exist."""
        mock_session = MagicMock()
        mock_session.get.return_value = make_mock_response(404, {"message": "Not Found"})
        mocker.patch("backend.services.github_service.requests.Session", return_value=mock_session)

        service = GitHubService()
        result = service.check_repository_exists("nonexistent-user-xyz", "nonexistent-repo-xyz")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_authentication_failure(self, mocker):
        """A 401 response means the token is invalid."""
        mock_session = MagicMock()
        mock_session.get.return_value = make_mock_response(401, {"message": "Bad credentials"})
        mocker.patch("backend.services.github_service.requests.Session", return_value=mock_session)

        service = GitHubService()
        result = service.check_repository_exists("owner", "repo")

        assert result["success"] is False
        assert "auth" in result["error"].lower()

    def test_rate_limit_error(self, mocker):
        """A 429 response means we've hit the rate limit."""
        mock_session = MagicMock()
        mock_session.get.return_value = make_mock_response(
            429, {}, headers={"X-RateLimit-Reset": "9999999999"}
        )
        mocker.patch("backend.services.github_service.requests.Session", return_value=mock_session)

        service = GitHubService()
        result = service.check_repository_exists("owner", "repo")

        assert result["success"] is False
        assert "rate limit" in result["error"].lower()

    def test_network_error(self, mocker):
        """A ConnectionError should return a clean error, not crash."""
        import requests as req
        mock_session = MagicMock()
        mock_session.get.side_effect = req.exceptions.ConnectionError("Connection refused")
        mocker.patch("backend.services.github_service.requests.Session", return_value=mock_session)

        service = GitHubService()
        result = service.check_repository_exists("owner", "repo")

        assert result["success"] is False
        assert "network" in result["error"].lower() or "connection" in result["error"].lower()

    def test_timeout_error(self, mocker):
        """A Timeout should return a clean error, not crash."""
        import requests as req
        mock_session = MagicMock()
        mock_session.get.side_effect = req.exceptions.Timeout("Request timed out")
        mocker.patch("backend.services.github_service.requests.Session", return_value=mock_session)

        service = GitHubService()
        result = service.check_repository_exists("owner", "repo")

        assert result["success"] is False
        assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()


class TestGitHubServiceGetRepository:
    """Tests for get_repository()."""

    def test_successful_metadata_fetch(self, mocker):
        """A 200 response with full repo data should parse correctly."""
        fake_repo = {
            "name": "requests",
            "full_name": "psf/requests",
            "owner": {"login": "psf"},
            "description": "A simple HTTP library",
            "html_url": "https://github.com/psf/requests",
            "url": "https://api.github.com/repos/psf/requests",
            "default_branch": "main",
            "language": "Python",
            "languages_url": "https://api.github.com/repos/psf/requests/languages",
            "stargazers_count": 50000,
            "forks_count": 9000,
            "watchers_count": 50000,
            "open_issues_count": 100,
            "size": 15000,
            "license": {"name": "Apache License 2.0"},
            "created_at": "2011-02-13T18:38:27Z",
            "updated_at": "2023-09-01T10:00:00Z",
            "pushed_at": "2023-09-01T10:00:00Z",
            "archived": False,
            "fork": False,
            "topics": ["python", "http", "requests"],
        }

        mock_session = MagicMock()
        mock_session.get.return_value = make_mock_response(200, fake_repo)
        mocker.patch("backend.services.github_service.requests.Session", return_value=mock_session)

        service = GitHubService()
        result = service.get_repository("psf", "requests")

        assert result["success"] is True
        data = result["data"]
        assert data["name"] == "requests"
        assert data["owner"] == "psf"
        assert data["stars"] == 50000
        assert data["language"] == "Python"
        assert data["license"] == "Apache License 2.0"
        assert data["is_archived"] is False

    def test_repo_with_no_license(self, mocker):
        """Repositories without a license should not crash."""
        fake_repo = {
            "name": "my-repo",
            "full_name": "user/my-repo",
            "owner": {"login": "user"},
            "description": None,
            "html_url": "https://github.com/user/my-repo",
            "url": "https://api.github.com/repos/user/my-repo",
            "default_branch": "main",
            "language": None,     # No detected language
            "languages_url": "...",
            "stargazers_count": 0,
            "forks_count": 0,
            "watchers_count": 0,
            "open_issues_count": 0,
            "size": 0,
            "license": None,      # No license
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "pushed_at": "2023-01-01T00:00:00Z",
            "archived": False,
            "fork": False,
            "topics": [],
        }

        mock_session = MagicMock()
        mock_session.get.return_value = make_mock_response(200, fake_repo)
        mocker.patch("backend.services.github_service.requests.Session", return_value=mock_session)

        service = GitHubService()
        result = service.get_repository("user", "my-repo")

        assert result["success"] is True
        assert result["data"]["license"] is None
        assert result["data"]["language"] is None
        assert result["data"]["description"] is None

    def test_repo_not_found(self, mocker):
        """404 should return a clean not-found error."""
        mock_session = MagicMock()
        mock_session.get.return_value = make_mock_response(404, {"message": "Not Found"})
        mocker.patch("backend.services.github_service.requests.Session", return_value=mock_session)

        service = GitHubService()
        result = service.get_repository("ghost", "nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"].lower()


class TestGitHubServiceGetCommits:
    """Tests for get_commits()."""

    def test_fetches_commits_single_page(self, mocker):
        """Single page of commits (less than per_page items) should work."""
        fake_commits = [
            {"sha": "abc123", "commit": {"message": "Initial commit", "author": {"date": "2023-01-01"}}},
            {"sha": "def456", "commit": {"message": "Add feature", "author": {"date": "2023-01-02"}}},
        ]

        mock_session = MagicMock()
        mock_response = make_mock_response(200, fake_commits, headers={"Link": ""})
        mock_session.get.return_value = mock_response
        mocker.patch("backend.services.github_service.requests.Session", return_value=mock_session)

        service = GitHubService()
        result = service.get_commits("owner", "repo")

        assert result["success"] is True
        assert len(result["data"]) == 2
        assert result["data"][0]["sha"] == "abc123"

    def test_empty_commit_history(self, mocker):
        """Repository with no commits should return success with empty list."""
        mock_session = MagicMock()
        mock_response = make_mock_response(200, [], headers={"Link": ""})
        # Explicitly set ok=True so the paginator doesn't fall into the dict branch
        mock_response.ok = True
        mock_session.get.return_value = mock_response
        mocker.patch("backend.services.github_service.requests.Session", return_value=mock_session)

        service = GitHubService()
        result = service.get_commits("owner", "empty-repo")

        assert result["success"] is True
        assert result["data"] == []
