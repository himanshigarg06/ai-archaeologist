"""
tests/test_validators.py — Tests for GitHub URL Validation
============================================================
Purpose:
    Verifies that validate_github_url() correctly accepts valid URLs
    and rejects invalid ones.

Why testing matters here:
    The validator is the first thing that runs when a user submits a URL.
    If it's wrong — too strict (rejects good URLs) or too loose (accepts
    bad URLs) — everything downstream breaks.

    These tests catch bugs without needing to start Flask or call GitHub.

How to run:
    From the ai-archaeologist/ directory (with venv active):
        pytest tests/test_validators.py -v

Understanding pytest:
    - Each function starting with test_ is automatically discovered and run.
    - assert checks a condition — if it's False, the test fails.
    - The -v flag shows each test name and pass/fail individually.
"""

import sys
import os

# Add the project root to sys.path so Python can find the backend package.
# This is needed when running pytest from the ai-archaeologist/ directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils.validators import validate_github_url, extract_owner_repo


# ===========================================================================
# VALID URL TESTS
# Tests that should return valid=True and correct owner/repo values
# ===========================================================================

class TestValidUrls:
    """Tests for URLs that should be accepted."""

    def test_standard_https_url(self):
        """The most common URL format should work."""
        result = validate_github_url("https://github.com/kennethreitz/requests")
        assert result["valid"] is True
        assert result["owner"] == "kennethreitz"
        assert result["repo"] == "requests"

    def test_url_with_trailing_slash(self):
        """Trailing slash is common when copying from the browser — must be accepted."""
        result = validate_github_url("https://github.com/kennethreitz/requests/")
        assert result["valid"] is True
        assert result["owner"] == "kennethreitz"
        assert result["repo"] == "requests"

    def test_url_without_protocol(self):
        """Some users type github.com/owner/repo without https:// — should work."""
        result = validate_github_url("github.com/django/django")
        assert result["valid"] is True
        assert result["owner"] == "django"
        assert result["repo"] == "django"

    def test_url_with_http(self):
        """http:// (not https) should also be accepted."""
        result = validate_github_url("http://github.com/pallets/flask")
        assert result["valid"] is True
        assert result["owner"] == "pallets"
        assert result["repo"] == "flask"

    def test_url_with_trailing_path(self):
        """URLs with extra path segments (e.g. /tree/main) should strip to just owner/repo."""
        result = validate_github_url("https://github.com/torvalds/linux/tree/master")
        assert result["valid"] is True
        assert result["owner"] == "torvalds"
        assert result["repo"] == "linux"

    def test_repo_with_hyphens(self):
        """Repository names with hyphens are valid on GitHub."""
        result = validate_github_url("https://github.com/psf/black")
        assert result["valid"] is True
        assert result["owner"] == "psf"
        assert result["repo"] == "black"

    def test_repo_with_dots(self):
        """Repository names with dots are valid (e.g. username.github.io)."""
        result = validate_github_url("https://github.com/someuser/someuser.github.io")
        assert result["valid"] is True
        assert result["owner"] == "someuser"
        assert result["repo"] == "someuser.github.io"

    def test_git_suffix_stripped(self):
        """Clone URLs end in .git — this should be stripped from the repo name."""
        result = validate_github_url("https://github.com/django/django.git")
        assert result["valid"] is True
        assert result["repo"] == "django"   # .git removed

    def test_url_with_leading_whitespace(self):
        """Users sometimes paste URLs with accidental spaces — should be stripped."""
        result = validate_github_url("  https://github.com/requests/requests  ")
        assert result["valid"] is True
        assert result["owner"] == "requests"
        assert result["repo"] == "requests"

    def test_url_with_uppercase(self):
        """GitHub.COM in caps should still match (case-insensitive)."""
        result = validate_github_url("https://GITHUB.COM/owner/repo")
        assert result["valid"] is True
        assert result["owner"] == "owner"
        assert result["repo"] == "repo"

    def test_numeric_owner_and_repo(self):
        """Numeric characters in owner/repo names are allowed by GitHub."""
        result = validate_github_url("https://github.com/user123/project456")
        assert result["valid"] is True
        assert result["owner"] == "user123"
        assert result["repo"] == "project456"


# ===========================================================================
# INVALID URL TESTS
# Tests that should return valid=False with an error message
# ===========================================================================

class TestInvalidUrls:
    """Tests for URLs that should be rejected."""

    def test_empty_string(self):
        """Empty string is not a URL."""
        result = validate_github_url("")
        assert result["valid"] is False
        assert "error" in result

    def test_none_input(self):
        """None input should be handled gracefully, not crash."""
        result = validate_github_url(None)
        assert result["valid"] is False
        assert "error" in result

    def test_whitespace_only(self):
        """A string of only spaces should be treated as empty."""
        result = validate_github_url("   ")
        assert result["valid"] is False
        assert "error" in result

    def test_non_github_url(self):
        """GitLab or other hosts should be rejected."""
        result = validate_github_url("https://gitlab.com/owner/repo")
        assert result["valid"] is False
        assert "error" in result

    def test_bitbucket_url(self):
        """Bitbucket URLs should be rejected."""
        result = validate_github_url("https://bitbucket.org/owner/repo")
        assert result["valid"] is False

    def test_missing_repo_name(self):
        """URL with only owner but no repo should be rejected."""
        result = validate_github_url("https://github.com/torvalds")
        assert result["valid"] is False
        assert "error" in result

    def test_missing_owner_and_repo(self):
        """Just the GitHub domain with no path is invalid."""
        result = validate_github_url("https://github.com/")
        assert result["valid"] is False

    def test_plain_text(self):
        """Random text with no URL structure should be rejected."""
        result = validate_github_url("hello world this is not a url")
        assert result["valid"] is False

    def test_random_website(self):
        """A completely unrelated URL should be rejected."""
        result = validate_github_url("https://google.com/search?q=github")
        assert result["valid"] is False

    def test_github_gist_url(self):
        """gist.github.com is not a repository URL."""
        result = validate_github_url("https://gist.github.com/owner/abc123")
        assert result["valid"] is False

    def test_integer_input(self):
        """Non-string input should be handled gracefully."""
        result = validate_github_url(12345)
        assert result["valid"] is False
        assert "error" in result


# ===========================================================================
# EXTRACT OWNER/REPO HELPER TESTS
# ===========================================================================

class TestExtractOwnerRepo:
    """Tests for the extract_owner_repo() convenience function."""

    def test_valid_url_returns_tuple(self):
        """Valid URL should return a (owner, repo) tuple."""
        result = extract_owner_repo("https://github.com/pallets/flask")
        assert result is not None
        owner, repo = result
        assert owner == "pallets"
        assert repo == "flask"

    def test_invalid_url_returns_none(self):
        """Invalid URL should return None (not raise an exception)."""
        result = extract_owner_repo("not-a-url")
        assert result is None

    def test_empty_url_returns_none(self):
        """Empty string should return None."""
        result = extract_owner_repo("")
        assert result is None
