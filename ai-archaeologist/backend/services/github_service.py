"""
services/github_service.py — GitHub API Communication Layer
=============================================================
Purpose:
    This is the ONLY file in the project that talks directly to GitHub's
    REST API. All other services call methods on GitHubService —
    they never make HTTP requests themselves.

    This separation means:
        - If GitHub changes their API, we only update this one file.
        - We can mock this class in tests without touching other files.
        - Authentication and headers are set up in one place only.

Design:
    GitHubService is a simple class. When you create an instance, it:
        1. Loads the GitHub token from config
        2. Creates a persistent requests.Session
        3. Sets the Authorization header once for all requests

    Then you call methods like:
        service.get_repository("django", "django")
        service.get_commits("django", "django")
        service.get_contributors("django", "django")
        ... etc.

    Each method returns a dictionary:
        On success: {"success": True, "data": [...]}
        On error:   {"success": False, "error": "...", "details": "..."}

Why requests.Session?
    A Session object reuses the underlying TCP connection across multiple
    requests. This is faster than creating a new connection for every call.
    It also lets us set headers (like Authorization) once instead of
    repeating them on every request.

Student note — why not PyGitHub?
    PyGitHub is a wrapper library around the GitHub API. It's convenient
    but hides how the API actually works. Using raw requests means you
    can see exactly what URL is being called and what is being returned.
    This is better for a learning project and for your portfolio interviews.
"""

import logging
import requests

from backend.config import Config
from backend.utils.github_helpers import (
    fetch_all_pages,
    is_rate_limited,
    get_rate_limit_reset_time,
    make_error,
    make_success,
)

logger = logging.getLogger(__name__)


class GitHubService:
    """
    Handles all communication with the GitHub REST API.

    Usage:
        service = GitHubService()
        result = service.get_repository("torvalds", "linux")
        if result["success"]:
            data = result["data"]
        else:
            print(result["error"])
    """

    def __init__(self):
        """
        Set up the HTTP session with authentication headers.

        We use a requests.Session so that:
            - The Authorization header is set once and reused everywhere
            - The underlying TCP connection is reused (faster)
            - Timeout is applied consistently
        """
        self.base_url = Config.GITHUB_API_BASE_URL
        self.timeout = Config.GITHUB_REQUEST_TIMEOUT
        self.max_pages = Config.MAX_PAGES_PER_REQUEST
        self.per_page = Config.ITEMS_PER_PAGE

        # Create the session
        self.session = requests.Session()

        # Set headers that every GitHub API request should include
        self.session.headers.update({
            # Token authentication — 5000 req/hour vs 60 without token
            "Authorization": f"Bearer {Config.GITHUB_TOKEN}",

            # Tell GitHub we want JSON responses
            "Accept": "application/vnd.github+json",

            # Pins us to a specific stable API version
            "X-GitHub-Api-Version": "2022-11-28",
        })

        # Attach the timeout to the session using an adapter hook
        # This avoids repeating timeout= on every .get() call
        self._timeout = self.timeout

        logger.info("GitHubService initialised (session created with auth headers).")

    def _get(self, url: str, params: dict = None) -> tuple:
        """
        Internal helper: makes a single GET request with error handling.

        This is the lowest-level method — all public methods call this
        (or fetch_all_pages which also uses self.session.get).

        Args:
            url (str):      Full URL to request.
            params (dict):  Optional query parameters.

        Returns:
            tuple: (response_or_None, error_dict_or_None)
            - On success: (response, None)
            - On error:   (None, {"success": False, "error": ..., "details": ...})
        """
        try:
            response = self.session.get(url, params=params, timeout=self._timeout)
        except requests.exceptions.ConnectionError:
            return None, make_error(
                "Network connection failed",
                "Could not connect to the GitHub API. Check your internet connection."
            )
        except requests.exceptions.Timeout:
            return None, make_error(
                "Request timed out",
                f"GitHub API did not respond within {self._timeout} seconds."
            )
        except requests.exceptions.RequestException as e:
            return None, make_error(
                "Request failed",
                f"Unexpected network error: {str(e)}"
            )

        # Check for rate limiting before other status codes
        if is_rate_limited(response):
            reset_time = get_rate_limit_reset_time(response)
            return None, make_error(
                "GitHub API rate limit reached",
                f"You have exceeded the GitHub API rate limit. "
                f"It will reset at: {reset_time}. "
                f"Consider waiting or using a token with higher limits."
            )

        return response, None

    # -----------------------------------------------------------------------
    # Public API methods
    # -----------------------------------------------------------------------

    def check_repository_exists(self, owner: str, repo: str) -> dict:
        """
        Check whether a GitHub repository exists and is accessible.

        Makes a HEAD-style check using the repos endpoint.
        Returns before fetching any real data — used as a fast pre-check.

        Args:
            owner (str): Repository owner (username or org name).
            repo (str):  Repository name.

        Returns:
            dict:
                {"success": True}  if the repo exists and is accessible
                {"success": False, "error": ..., "details": ...}  otherwise
        """
        url = f"{self.base_url}/repos/{owner}/{repo}"
        logger.info(f"Checking if repository exists: {owner}/{repo}")

        response, error = self._get(url)
        if error:
            return error

        if response.status_code == 200:
            return make_success({"exists": True})
        elif response.status_code == 404:
            return make_error(
                "Repository not found",
                f"The repository '{owner}/{repo}' does not exist on GitHub "
                f"or it is private and cannot be accessed with your token."
            )
        elif response.status_code == 401:
            return make_error(
                "Authentication failed",
                "Your GitHub token is invalid or has expired. "
                "Please generate a new token and update your .env file."
            )
        elif response.status_code == 403:
            return make_error(
                "Access forbidden",
                f"You do not have permission to access '{owner}/{repo}'. "
                f"It may be a private repository."
            )
        else:
            return make_error(
                "Unexpected GitHub API response",
                f"GitHub returned status code {response.status_code}."
            )

    def get_repository(self, owner: str, repo: str) -> dict:
        """
        Fetch repository metadata from GitHub.

        Calls: GET /repos/{owner}/{repo}

        Returns all available metadata fields. Missing optional fields
        (like license or description) are handled gracefully.

        Args:
            owner (str): Repository owner.
            repo (str):  Repository name.

        Returns:
            dict with success=True and "data" key containing repo metadata,
            or success=False with error information.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}"
        logger.info(f"Fetching repository metadata: {owner}/{repo}")

        response, error = self._get(url)
        if error:
            return error

        if response.status_code == 404:
            return make_error(
                "Repository not found",
                f"'{owner}/{repo}' does not exist or is not accessible."
            )

        if not response.ok:
            return make_error(
                "Failed to fetch repository",
                f"GitHub returned status {response.status_code}."
            )

        try:
            raw = response.json()
        except Exception:
            return make_error("Invalid response", "GitHub returned non-JSON data.")

        # Extract fields carefully — use .get() for everything that might be missing
        # GitHub does not guarantee all fields are present for all repositories
        data = {
            "name":              raw.get("name"),
            "full_name":         raw.get("full_name"),
            "owner":             raw.get("owner", {}).get("login"),
            "description":       raw.get("description"),          # can be None
            "url":               raw.get("html_url"),
            "api_url":           raw.get("url"),
            "default_branch":    raw.get("default_branch"),
            "language":          raw.get("language"),             # can be None
            "languages_url":     raw.get("languages_url"),        # fetch separately
            "stars":             raw.get("stargazers_count", 0),
            "forks":             raw.get("forks_count", 0),
            "watchers":          raw.get("watchers_count", 0),
            "open_issues_count": raw.get("open_issues_count", 0),
            "size_kb":           raw.get("size", 0),
            "license":           raw.get("license", {}).get("name") if raw.get("license") else None,
            "created_at":        raw.get("created_at"),
            "updated_at":        raw.get("updated_at"),
            "pushed_at":         raw.get("pushed_at"),
            "is_archived":       raw.get("archived", False),
            "is_fork":           raw.get("fork", False),
            "topics":            raw.get("topics", []),
        }

        return make_success({"data": data})

    def get_languages(self, owner: str, repo: str) -> dict:
        """
        Fetch the breakdown of programming languages used in the repository.

        Calls: GET /repos/{owner}/{repo}/languages

        Returns:
            dict like {"Python": 45231, "JavaScript": 12033, ...}
            where values are byte counts.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/languages"
        logger.info(f"Fetching languages: {owner}/{repo}")

        response, error = self._get(url)
        if error:
            return error

        if not response.ok:
            return make_error("Failed to fetch languages", f"Status {response.status_code}.")

        try:
            data = response.json()
        except Exception:
            return make_error("Invalid response", "GitHub returned non-JSON data.")

        return make_success({"data": data})

    def get_commits(self, owner: str, repo: str) -> dict:
        """
        Fetch the full commit history of the repository.

        Calls: GET /repos/{owner}/{repo}/commits  (paginated)

        GitHub returns up to 100 commits per page. We fetch all pages
        up to the MAX_PAGES_PER_REQUEST limit defined in Config.

        Args:
            owner (str): Repository owner.
            repo (str):  Repository name.

        Returns:
            dict with success=True and "data" as a list of commit objects,
            or success=False with error information.

        Student note:
            Each commit object in the list is the "summary" form — it does
            NOT include per-file changes. To get additions/deletions per file,
            you need to call get_commit_detail() for each SHA.
            We do that in commit_service.py (Step 9).
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        params = {"per_page": self.per_page}
        logger.info(f"Fetching commits: {owner}/{repo} (max {self.max_pages} pages)")

        items, error = fetch_all_pages(self.session, url, params, self.max_pages)

        if error and not items:
            return make_error("Failed to fetch commits", error)

        logger.info(f"Fetched {len(items)} commits for {owner}/{repo}")
        return make_success({"data": items, "warning": error})  # warning=None if no error

    def get_commit_detail(self, owner: str, repo: str, sha: str) -> dict:
        """
        Fetch detailed information for a single commit by SHA.

        Calls: GET /repos/{owner}/{repo}/commits/{sha}

        This endpoint returns the full commit data including:
            - files changed
            - additions per file
            - deletions per file
            - total changes

        Args:
            owner (str): Repository owner.
            repo (str):  Repository name.
            sha (str):   The commit SHA (40-character hash).

        Returns:
            dict with success=True and "data" as the detailed commit object.

        Student note:
            This is an expensive call — one HTTP request per commit.
            commit_service.py (Step 9) only calls this selectively to
            avoid hitting rate limits on repositories with many commits.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{sha}"
        logger.debug(f"Fetching commit detail: {sha[:8]}...")

        response, error = self._get(url)
        if error:
            return error

        if response.status_code == 422:
            # GitHub returns 422 for commits it cannot process (e.g. too large diffs)
            return make_error(
                "Commit detail unavailable",
                f"GitHub cannot return detail for commit {sha} (possibly a very large commit)."
            )

        if not response.ok:
            return make_error("Failed to fetch commit detail", f"Status {response.status_code}.")

        try:
            data = response.json()
        except Exception:
            return make_error("Invalid response", "GitHub returned non-JSON data.")

        return make_success({"data": data})

    def get_contributors(self, owner: str, repo: str) -> dict:
        """
        Fetch the list of contributors to the repository.

        Calls: GET /repos/{owner}/{repo}/contributors  (paginated)

        Includes bots (e.g. Dependabot, github-actions[bot]) — we record
        all contributors and leave classification to a later phase.

        Args:
            owner (str): Repository owner.
            repo (str):  Repository name.

        Returns:
            dict with success=True and "data" as a list of contributor objects.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/contributors"
        # anon=true includes anonymous contributors (those without GitHub accounts)
        params = {"per_page": self.per_page, "anon": "true"}
        logger.info(f"Fetching contributors: {owner}/{repo}")

        items, error = fetch_all_pages(self.session, url, params, self.max_pages)

        if error and not items:
            return make_error("Failed to fetch contributors", error)

        logger.info(f"Fetched {len(items)} contributors for {owner}/{repo}")
        return make_success({"data": items, "warning": error})

    def get_issues(self, owner: str, repo: str) -> dict:
        """
        Fetch all issues from the repository (open and closed).

        Calls: GET /repos/{owner}/{repo}/issues  (paginated)

        IMPORTANT: GitHub's issues endpoint also returns pull requests.
        We filter those out in issue_service.py by checking for the
        "pull_request" key in each item.

        Args:
            owner (str): Repository owner.
            repo (str):  Repository name.

        Returns:
            dict with success=True and "data" as a list of issue objects.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        # state=all fetches both open and closed issues
        params = {"per_page": self.per_page, "state": "all"}
        logger.info(f"Fetching issues: {owner}/{repo}")

        items, error = fetch_all_pages(self.session, url, params, self.max_pages)

        if error and not items:
            return make_error("Failed to fetch issues", error)

        logger.info(f"Fetched {len(items)} issues/PRs (before filtering) for {owner}/{repo}")
        return make_success({"data": items, "warning": error})

    def get_pull_requests(self, owner: str, repo: str) -> dict:
        """
        Fetch all pull requests from the repository (open, closed, merged).

        Calls: GET /repos/{owner}/{repo}/pulls  (paginated)

        Unlike the issues endpoint, this endpoint returns ONLY pull requests.
        To get merged PRs, we must request state=closed and check merged_at.

        Args:
            owner (str): Repository owner.
            repo (str):  Repository name.

        Returns:
            dict with success=True and "data" as a list of PR objects.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        # state=all fetches open + closed (closed includes merged)
        params = {"per_page": self.per_page, "state": "all"}
        logger.info(f"Fetching pull requests: {owner}/{repo}")

        items, error = fetch_all_pages(self.session, url, params, self.max_pages)

        if error and not items:
            return make_error("Failed to fetch pull requests", error)

        logger.info(f"Fetched {len(items)} pull requests for {owner}/{repo}")
        return make_success({"data": items, "warning": error})

    def get_file_tree(self, owner: str, repo: str, branch: str = None) -> dict:
        """
        Fetch the complete file/directory tree of the repository.

        Calls: GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1

        This returns metadata for every file and directory in the repo —
        paths, types (blob/tree), sizes, and SHAs — without downloading
        any file content. Perfect for Phase 1.

        Args:
            owner (str):  Repository owner.
            repo (str):   Repository name.
            branch (str): Branch name (uses default branch if None).

        Returns:
            dict with success=True and "data" as a list of tree entries.

        Student note:
            recursive=1 means GitHub returns the entire tree in one response,
            not just the top-level directory. This is more efficient than
            making recursive directory calls.

            The downside: for very large repos, GitHub may return
            "truncated": true in the response. We detect and log this.
        """
        # Use "HEAD" as a shorthand for the default branch
        branch_ref = branch or "HEAD"
        url = f"{self.base_url}/repos/{owner}/{repo}/git/trees/{branch_ref}"
        params = {"recursive": "1"}
        logger.info(f"Fetching file tree: {owner}/{repo} @ {branch_ref}")

        response, error = self._get(url, params=params)
        if error:
            return error

        if response.status_code == 404:
            return make_error(
                "File tree not found",
                f"Could not find the file tree for '{owner}/{repo}'. "
                f"The repository may be empty or the branch may not exist."
            )

        if response.status_code == 409:
            # GitHub returns 409 (Conflict) for empty repositories
            return make_error(
                "Repository is empty",
                f"'{owner}/{repo}' appears to be an empty repository with no commits."
            )

        if not response.ok:
            return make_error("Failed to fetch file tree", f"Status {response.status_code}.")

        try:
            data = response.json()
        except Exception:
            return make_error("Invalid response", "GitHub returned non-JSON data.")

        tree_items = data.get("tree", [])
        is_truncated = data.get("truncated", False)

        if is_truncated:
            logger.warning(
                f"File tree for {owner}/{repo} was TRUNCATED by GitHub. "
                f"The repository is very large. Only partial tree data was returned."
            )

        logger.info(f"Fetched {len(tree_items)} file tree entries for {owner}/{repo}")
        return make_success({
            "data": tree_items,
            "truncated": is_truncated
        })

    def get_rate_limit_status(self) -> dict:
        """
        Check the current GitHub API rate limit status.

        Useful for debugging — tells you how many requests remain.

        Returns:
            dict with rate limit info or an error.
        """
        url = f"{self.base_url}/rate_limit"
        response, error = self._get(url)
        if error:
            return error

        try:
            data = response.json()
            core = data.get("resources", {}).get("core", {})
            return make_success({
                "limit":     core.get("limit"),
                "remaining": core.get("remaining"),
                "used":      core.get("used"),
                "reset":     core.get("reset"),
            })
        except Exception:
            return make_error("Failed to parse rate limit response.")
