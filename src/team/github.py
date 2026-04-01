"""GitHub repository helper.

Requires environment variables:
  GITHUB_TOKEN     — Personal Access Token (or fine-grained token) with `repo` scope
  GITHUB_USERNAME  — Your GitHub username (used to check whether repo already exists)
  GITHUB_ORG       — (optional) Create repos under this org instead of the authenticated user
"""

import base64
import hashlib
import hmac
import logging
import os
import re

import httpx

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Events we subscribe to on each repo webhook
_WEBHOOK_EVENTS = [
    "pull_request",
    "pull_request_review",
    "pull_request_review_comment",
    "issue_comment",
]


def verify_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """Return True if the request signature matches GITHUB_WEBHOOK_SECRET."""
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "").strip()
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET is not set — rejecting webhook")
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")


def is_dev_agent(username: str) -> bool:
    """Return True if *username* is the configured dev-agent bot account."""
    dev_bot = os.environ.get("DEV_GITHUB_USERNAME", "").strip()
    return bool(dev_bot and username == dev_bot)


def parse_pr_comment_event(event: str, payload: dict) -> dict | None:
    """
    Normalise pull_request_review_comment, pull_request_review, and issue_comment events.

    Returns a dict with keys:
        pr_url, pr_number, repo_full_name, commenter, body, comment_url, event_type
        For review_comment events also includes: comment_id (int)
    or None if this payload should be ignored (wrong action, empty body, not a PR, etc.).
    """
    action = payload.get("action", "")

    if event == "pull_request_review_comment":
        if action != "created":
            return None
        comment = payload.get("comment", {})
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        return {
            "pr_url": pr.get("html_url", ""),
            "pr_number": pr.get("number"),
            "repo_full_name": repo.get("full_name", ""),
            "commenter": comment.get("user", {}).get("login", ""),
            "body": comment.get("body", ""),
            "comment_url": comment.get("html_url", ""),
            "comment_id": comment.get("id"),   # used to reply in the review thread
            "event_type": "review_comment",
        }

    if event == "pull_request_review":
        if action != "submitted":
            return None
        review = payload.get("review", {})
        body = (review.get("body") or "").strip()
        if not body:
            return None  # approve/request-changes with no textual comment
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        return {
            "pr_url": pr.get("html_url", ""),
            "pr_number": pr.get("number"),
            "repo_full_name": repo.get("full_name", ""),
            "commenter": review.get("user", {}).get("login", ""),
            "body": body,
            "comment_url": review.get("html_url", ""),
            "event_type": "review",
        }

    if event == "issue_comment":
        if action != "created":
            return None
        issue = payload.get("issue", {})
        if "pull_request" not in issue:
            return None  # plain issue comment, not a PR
        comment = payload.get("comment", {})
        repo = payload.get("repository", {})
        pr_url = issue.get("pull_request", {}).get("html_url", "")
        return {
            "pr_url": pr_url,
            "pr_number": issue.get("number"),
            "repo_full_name": repo.get("full_name", ""),
            "commenter": comment.get("user", {}).get("login", ""),
            "body": comment.get("body", ""),
            "comment_url": comment.get("html_url", ""),
            "event_type": "pr_comment",
        }

    return None


def post_pr_comment(repo_full_name: str, pr_number: int, body: str) -> None:
    """Post a comment on a pull request via the GitHub REST API."""
    token = os.environ.get("DEV_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("Cannot post PR comment: no GitHub token configured")
        return
    headers = {**_HEADERS, "Authorization": f"Bearer {token}"}
    resp = httpx.post(
        f"{_GITHUB_API}/repos/{repo_full_name}/issues/{pr_number}/comments",
        json={"body": body},
        headers=headers,
        timeout=15,
    )
    resp.raise_for_status()
    logger.info("Posted comment on PR #%d in %s", pr_number, repo_full_name)


def register_webhook(full_name: str, headers: dict) -> None:
    """Register the project webhook on *full_name* if configured."""
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "").strip()
    base_url = os.environ.get("APP_BASE_URL", "").strip().rstrip("/")
    if not secret or not base_url:
        logger.info("Skipping webhook registration (GITHUB_WEBHOOK_SECRET or APP_BASE_URL not set)")
        return

    webhook_url = f"{base_url}/api/github/webhook/"
    resp = httpx.post(
        f"{_GITHUB_API}/repos/{full_name}/hooks",
        json={
            "name": "web",
            "active": True,
            "events": _WEBHOOK_EVENTS,
            "config": {
                "url": webhook_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0",
            },
        },
        headers=headers,
        timeout=15,
    )
    # 422 means webhook already exists — not an error
    if resp.status_code == 422:
        logger.info("Webhook already registered on %s", full_name)
        return
    resp.raise_for_status()
    logger.info("Webhook registered on %s → %s", full_name, webhook_url)


def _slugify(name: str) -> str:
    """Convert a project name to a valid GitHub repository name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s._-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-") or "project"


def _write_readme(full_name: str, content: str, headers: dict) -> None:
    """Create or replace README.md in the given repo with *content*."""
    encoded = base64.b64encode(content.encode()).decode()
    url = f"{_GITHUB_API}/repos/{full_name}/contents/README.md"

    # Fetch current SHA (auto_init creates a default README we need to overwrite).
    resp = httpx.get(url, headers=headers, timeout=15)
    payload: dict = {"message": "docs: add tech spec to README", "content": encoded}
    if resp.status_code == 200:
        payload["sha"] = resp.json()["sha"]

    put_resp = httpx.put(url, json=payload, headers=headers, timeout=15)
    put_resp.raise_for_status()
    logger.info("README written for %s", full_name)


def _upsert_collaborator(full_name: str, username: str, headers: dict) -> None:
    """Add *username* as a write collaborator on *full_name* (idempotent)."""
    resp = httpx.put(
        f"{_GITHUB_API}/repos/{full_name}/collaborators/{username}",
        json={"permission": "push"},
        headers=headers,
        timeout=15,
    )
    # 201 = invited, 204 = already a collaborator — both are success
    if resp.status_code not in (201, 204):
        resp.raise_for_status()
    logger.info("Collaborator %s upserted on %s (status %d)", username, full_name, resp.status_code)


def upsert_github_repo(project_name: str, description: str = "", readme_content: str = "") -> str:
    """Create or return an existing GitHub repository for the given project.

    - If the repo already exists under the configured owner it is returned as-is.
    - Raises ``ValueError`` when ``GITHUB_TOKEN`` is not set.
    - Raises ``httpx.HTTPStatusError`` on unexpected GitHub API errors.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN is not configured")

    headers = {**_HEADERS, "Authorization": f"Bearer {token}"}
    repo_name = _slugify(project_name)
    org = os.environ.get("GITHUB_ORG", "").strip()
    username = os.environ.get("GITHUB_USERNAME", "").strip()
    owner = org or username

    dev_bot = os.environ.get("DEV_GITHUB_USERNAME", "").strip()

    def _maybe_add_collaborator(full_name: str) -> None:
        if dev_bot:
            try:
                _upsert_collaborator(full_name, dev_bot, headers)
            except Exception:
                logger.exception("Failed to add collaborator %s to %s", dev_bot, full_name)

    # Check whether the repo already exists before trying to create it.
    if owner:
        resp = httpx.get(
            f"{_GITHUB_API}/repos/{owner}/{repo_name}",
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            url = data["html_url"]
            logger.info("GitHub repo already exists: %s", url)
            _maybe_add_collaborator(data["full_name"])
            return url

    # Create the repo under the org (if set) or the authenticated user.
    create_url = (
        f"{_GITHUB_API}/orgs/{org}/repos"
        if org
        else f"{_GITHUB_API}/user/repos"
    )
    payload = {
        "name": repo_name,
        "description": (description[:350] if description else ""),
        "private": True,
        "auto_init": True,
    }
    resp = httpx.post(create_url, json=payload, headers=headers, timeout=15)

    # 422 with "name already exists" means the repo exists but we couldn't
    # find it above (e.g. GITHUB_USERNAME was not set). Fetch and return it.
    if resp.status_code == 422:
        errors = resp.json().get("errors", [])
        if any(e.get("message") == "name already exists on this account" for e in errors):
            if owner:
                existing = httpx.get(
                    f"{_GITHUB_API}/repos/{owner}/{repo_name}",
                    headers=headers,
                    timeout=15,
                )
                if existing.status_code == 200:
                    url = existing.json()["html_url"]
                    logger.info("GitHub repo already exists (fetched after 422): %s", url)
                    return url
        resp.raise_for_status()

    resp.raise_for_status()
    repo_data = resp.json()
    url = repo_data["html_url"]
    logger.info("Created GitHub repo: %s", url)
    if readme_content:
        try:
            _write_readme(repo_data["full_name"], readme_content, headers)
        except Exception:
            logger.exception("Failed to write README for %s", repo_data["full_name"])
    _maybe_add_collaborator(repo_data["full_name"])
    try:
        register_webhook(repo_data["full_name"], headers)
    except Exception:
        logger.exception("Failed to register webhook for %s", repo_data["full_name"])
    return url
