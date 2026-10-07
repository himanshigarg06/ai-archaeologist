"""
utils/github_helpers.py — GitHub API Helper Utilities
======================================================
Purpose:
    Reusable functions that support github_service.py.
    These are NOT API calls themselves — they are utilities that:
        - Detect rate-limit responses
        - Parse GitHub's pagination headers (Link header)
        - Fetch all pages of a paginated endpoint
        - Build consistent error result dictionaries

Why a separate helpers file?
    github_service.py would get very long if it contained both the
    API call logic AND all the pagination/error-handling machinery.
    Separating helpers keeps each file focused and testable on its own.

Student note — GitHub pagination:
    GitHub returns paginated results with a "Link" header that looks like:
        Link: <https://api.github.com/repos/.../commits?page=2>; rel="next",
              <https://api.github.com/repos/.../commits?page=14>; rel="last"

    We parse this header to know:
        - Is there a next page?
        - What is the URL for the next page?

    We keep fetching until there is no "next" link or we hit MAX_PAGES.
"""

import logging
import re

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate limit detection
# ---------------------------------------------------------------------------

def is_rate_limited(response) -> bool:
    """
    Check whether a GitHub API response indicates a rate limit error.

    GitHub returns HTTP 403 with a specific header, OR HTTP 429,
    when the rate limit is exceeded.

    Args:
        response: A requests.Response object.

    Returns:
        True if the response is a rate-limit error, False otherwise.
    """
    if response.status_code == 429:
        return True

    if response.status_code == 403:
        # GitHub sets X-RateLimit-Remaining to "0" when rate limited
        remaining = response.headers.get("X-RateLimit-Remaining", "1")
        if remaining == "0":
            return True

        # Also check the response body for the rate limit message
        try:
            body = response.json()
            message = body.get("message", "").lower()
            if "rate limit" in message or "api rate limit exceeded" in message:
                return True
        except Exception:
            pass

    return False


def get_rate_limit_reset_time(response) -> str:
    """
    Extract the rate limit reset time from GitHub's response headers.

    Args:
        response: A requests.Response object.

    Returns:
        A human-readable string with the reset timestamp, or a fallback message.
    """
    reset_timestamp = response.headers.get("X-RateLimit-Reset")
    if reset_timestamp:
        import datetime
        reset_time = datetime.datetime.fromtimestamp(int(reset_timestamp))
        return reset_time.strftime("%Y-%m-%d %H:%M:%S")
    return "unknown time (check GitHub API status)"


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------

def parse_next_page_url(link_header: str) -> str | None:
    """
    Parse GitHub's Link header to find the URL for the next page.

    GitHub's Link header looks like:
        <https://api.github.com/repos/owner/repo/commits?page=2>; rel="next",
        <https://api.github.com/repos/owner/repo/commits?page=14>; rel="last"

    We extract the URL where rel="next".

    Args:
        link_header (str): The value of the "Link" response header.

    Returns:
        The next page URL string, or None if there are no more pages.

    Student note:
        This regex finds: <URL>; rel="next"
        The URL is captured in group 1.
    """
    if not link_header:
        return None

    # Find the pattern: <...URL...>; rel="next"
    match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
    if match:
        return match.group(1)
    return None


def fetch_all_pages(session, url: str, params: dict, max_pages: int) -> tuple[list, str | None]:
    """
    Fetch all pages of a paginated GitHub API endpoint.

    GitHub returns results in pages. This function:
        1. Fetches the first page
        2. Checks for a "next" link in the response headers
        3. Keeps fetching until there is no "next" or max_pages is reached
        4. Combines all results into one list

    Args:
        session:    A requests.Session object (already has auth headers set).
        url:        The API endpoint URL (first page).
        params:     Query parameters (e.g. {"per_page": 100, "state": "all"}).
        max_pages:  Safety limit — stop after this many pages to avoid
                    accidentally fetching thousands of pages for huge repos.

    Returns:
        A tuple: (list_of_all_items, error_message_or_None)
        - On success: ([item1, item2, ...], None)
        - On error:   ([], "human-readable error string")

    Student note:
        We return an (items, error) tuple instead of raising exceptions.
        This keeps the calling code simple — just check if error is None.
    """
    all_items = []
    current_url = url
    page_number = 0

    while current_url and page_number < max_pages:
        page_number += 1
        logger.info(f"Fetching page {page_number}: {current_url}")

        try:
            response = session.get(current_url, params=params if page_number == 1 else None)
        except Exception as e:
            error_msg = f"Network error while fetching page {page_number}: {str(e)}"
            logger.error(error_msg)
            return all_items, error_msg

        # Check for rate limiting
        if is_rate_limited(response):
            reset_time = get_rate_limit_reset_time(response)
            error_msg = (
                f"GitHub API rate limit reached on page {page_number}. "
                f"Resets at: {reset_time}. "
                f"Returning {len(all_items)} items collected so far."
            )
            logger.warning(error_msg)
            # Return what we have so far, with the error message
            return all_items, error_msg

        # Check for other HTTP errors
        if response.status_code == 401:
            return [], "GitHub API authentication failed. Check your GITHUB_TOKEN in .env."

        if response.status_code == 404:
            return [], "GitHub resource not found."

        if not response.ok:
            error_msg = f"GitHub API returned status {response.status_code}: {response.text[:200]}"
            logger.error(error_msg)
            return all_items, error_msg

        # Parse the JSON response body
        try:
            page_data = response.json()
        except Exception as e:
            error_msg = f"Failed to parse GitHub API JSON response on page {page_number}: {str(e)}"
            logger.error(error_msg)
            return all_items, error_msg

        # GitHub returns either a list or a dict (for single-item endpoints)
        if isinstance(page_data, list):
            all_items.extend(page_data)
            logger.info(f"  → Got {len(page_data)} items (total so far: {len(all_items)})")
        else:
            # Single object response — just return it wrapped in a list
            all_items.append(page_data)
            break

        # If we got fewer items than per_page, this is the last page — no need to check the header
        per_page = params.get("per_page", 100) if page_number == 1 else 100
        if len(page_data) < per_page:
            logger.info("  → Last page reached (fewer items than per_page).")
            break

        # Check Link header for next page URL
        link_header = response.headers.get("Link", "")
        current_url = parse_next_page_url(link_header)

        if not current_url:
            logger.info("  → No more pages (no next link in header).")
            break

    if page_number >= max_pages and current_url:
        logger.warning(
            f"Reached MAX_PAGES limit ({max_pages}). "
            f"There may be more data. Increase MAX_PAGES_PER_REQUEST in config.py if needed."
        )

    return all_items, None


# ---------------------------------------------------------------------------
# Error response builders
# ---------------------------------------------------------------------------

def make_error(error: str, details: str = "") -> dict:
    """
    Build a consistent error response dictionary.

    All API error responses in this project use this format:
        {
            "success": False,
            "error": "Short description",
            "details": "Longer explanation (optional)"
        }

    Args:
        error (str):   Short human-readable error name.
        details (str): Longer explanation (optional).

    Returns:
        dict with success=False, error, and details keys.
    """
    return {
        "success": False,
        "error": error,
        "details": details
    }


def make_success(data: dict) -> dict:
    """
    Build a consistent success response dictionary.

    Args:
        data (dict): The payload to return alongside success=True.

    Returns:
        dict with success=True merged with data.
    """
    return {"success": True, **data}
