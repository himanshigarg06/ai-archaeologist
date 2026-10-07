"""
utils/validators.py — GitHub URL Validation
=============================================
Purpose:
    Validates and parses GitHub repository URLs before any API calls
    are made. Bad input is caught here — not deep inside a service.

Why this exists as a separate file:
    Validation logic is reused by the route (when a user submits a URL)
    and potentially by tests. Keeping it isolated makes it easy to test
    without starting Flask at all.

What this file does:
    - Accepts common GitHub URL formats
    - Extracts the owner and repository name
    - Rejects anything that isn't a valid GitHub repo URL
    - Returns a clean result dictionary

Accepted formats:
    https://github.com/owner/repo
    https://github.com/owner/repo/
    http://github.com/owner/repo
    github.com/owner/repo

Rejected:
    https://gitlab.com/owner/repo     ← wrong host
    https://github.com/owner          ← missing repo name
    https://github.com/               ← no owner or repo
    "hello world"                     ← not a URL at all
    ""                                ← empty string

Student note — why use regex here?
    A GitHub URL always has the same structure:
        [protocol://] github.com / owner / repo [/ anything-extra]
    A regular expression is the cleanest way to match this pattern
    and capture the owner/repo parts in one step.
"""

import re

# ---------------------------------------------------------------------------
# GitHub URL pattern
# ---------------------------------------------------------------------------
# Breaking it down piece by piece:
#
#   (https?://)?         → optional "http://" or "https://"
#   (www\.)?             → optional "www."
#   github\.com          → must contain github.com (the \. escapes the dot)
#   /                    → separator
#   ([a-zA-Z0-9_.-]+)   → owner: alphanumeric, underscores, dots, hyphens
#   /                    → separator
#   ([a-zA-Z0-9_.-]+)   → repo name: same character set
#   (/.*)?               → optional trailing path (e.g. /tree/main) — ignored
#   \s*$                 → optional whitespace at the end
#
# re.IGNORECASE makes it case-insensitive (GitHub.COM also matches).
GITHUB_URL_PATTERN = re.compile(
    r"^(https?://)?(www\.)?github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)(/.*)?$",
    re.IGNORECASE
)

# GitHub imposes these name length limits.
# We check them to catch obviously malformed inputs early.
MAX_OWNER_LENGTH = 39   # GitHub username limit
MAX_REPO_LENGTH = 100   # GitHub repository name limit


def validate_github_url(url: str) -> dict:
    """
    Validate a GitHub repository URL and extract owner and repo name.

    Args:
        url (str): The URL string submitted by the user.

    Returns:
        dict with one of these shapes:

        On success:
            {
                "valid": True,
                "owner": "kennethreitz",
                "repo": "requests"
            }

        On failure:
            {
                "valid": False,
                "error": "Human-readable error message"
            }

    Student note:
        Returning a dict (instead of raising an exception) keeps the
        calling code simple — the route just checks result["valid"]
        and doesn't need a try/except block.
    """
    # ----------------------------------------------------------------
    # Guard: empty or non-string input
    # ----------------------------------------------------------------
    if not url or not isinstance(url, str):
        return {
            "valid": False,
            "error": "URL is required and must be a non-empty string."
        }

    # Strip leading/trailing whitespace — users often accidentally add spaces
    url = url.strip()

    if not url:
        return {
            "valid": False,
            "error": "URL cannot be blank."
        }

    # ----------------------------------------------------------------
    # Guard: must contain github.com — fast rejection for obvious non-GitHub URLs
    # ----------------------------------------------------------------
    if "github.com" not in url.lower():
        return {
            "valid": False,
            "error": "URL must be a GitHub repository URL (e.g. https://github.com/owner/repo)."
        }

    # ----------------------------------------------------------------
    # Match against the full pattern
    # ----------------------------------------------------------------
    match = GITHUB_URL_PATTERN.match(url)

    if not match:
        return {
            "valid": False,
            "error": (
                "Invalid GitHub repository URL. "
                "Expected format: https://github.com/owner/repository"
            )
        }

    # match.group(3) = owner, match.group(4) = repo
    # (groups 1 and 2 are the protocol and www. prefixes)
    owner = match.group(3)
    repo = match.group(4)

    # ----------------------------------------------------------------
    # Guard: strip .git suffix if present (some users copy clone URLs)
    # e.g. https://github.com/owner/repo.git → repo = "repo"
    # ----------------------------------------------------------------
    if repo.endswith(".git"):
        repo = repo[:-4]

    # ----------------------------------------------------------------
    # Guard: length checks
    # ----------------------------------------------------------------
    if len(owner) > MAX_OWNER_LENGTH:
        return {
            "valid": False,
            "error": f"Owner name is too long (max {MAX_OWNER_LENGTH} characters)."
        }

    if len(repo) > MAX_REPO_LENGTH:
        return {
            "valid": False,
            "error": f"Repository name is too long (max {MAX_REPO_LENGTH} characters)."
        }

    # ----------------------------------------------------------------
    # Guard: empty owner or repo after parsing (shouldn't happen with
    # the regex, but defensive programming is good practice)
    # ----------------------------------------------------------------
    if not owner or not repo:
        return {
            "valid": False,
            "error": "Could not extract owner and repository name from URL."
        }

    # ----------------------------------------------------------------
    # All checks passed
    # ----------------------------------------------------------------
    return {
        "valid": True,
        "owner": owner,
        "repo": repo
    }


def extract_owner_repo(url: str) -> tuple[str, str] | None:
    """
    Convenience function — returns (owner, repo) tuple or None.

    Useful when you just want the values and don't need the full
    validation result dictionary.

    Args:
        url (str): The GitHub repository URL.

    Returns:
        tuple (owner, repo) if valid, or None if invalid.

    Example:
        owner, repo = extract_owner_repo("https://github.com/user/myrepo")
        # owner = "user", repo = "myrepo"
    """
    result = validate_github_url(url)
    if result["valid"]:
        return result["owner"], result["repo"]
    return None
