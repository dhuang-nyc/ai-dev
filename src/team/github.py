"""GitHub repository helper.

Requires environment variables:
  GITHUB_TOKEN     — Personal Access Token (or fine-grained token) with `repo` scope
  GITHUB_USERNAME  — Your GitHub username (used to check whether repo already exists)
  GITHUB_ORG       — (optional) Create repos under this org instead of the authenticated user
"""

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


def _slugify(name: str) -> str:
    """Convert a project name to a valid GitHub repository name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s._-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    return slug.strip("-") or "project"


def create_github_repo(project_name: str, description: str = "") -> str:
    """Create a GitHub repository for the given project and return its HTML URL.

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

    # Check whether the repo already exists before trying to create it.
    if owner:
        resp = httpx.get(
            f"{_GITHUB_API}/repos/{owner}/{repo_name}",
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            url = resp.json()["html_url"]
            logger.info("GitHub repo already exists: %s", url)
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
        "private": False,
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
    url = resp.json()["html_url"]
    logger.info("Created GitHub repo: %s", url)
    return url
