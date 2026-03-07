"""
Dev agent — pure functions, no Django ORM.
All subprocess calls happen here; tasks.py wires in DB state.
"""
import logging
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

WORKSPACES_BASE = os.environ.get("WORKSPACES_BASE", "/workspaces")
DEV_GITHUB_TOKEN = os.environ.get("DEV_GITHUB_TOKEN", "")
DEV_GIT_NAME = os.environ.get("DEV_GIT_NAME", "Dev Agent")
DEV_GIT_EMAIL = os.environ.get("DEV_GIT_EMAIL", "dev-agent@localhost")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> str:
    """Run a subprocess, return stdout+stderr, raise on non-zero exit."""
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(
            f"Command {cmd} failed (rc={result.returncode}):\n{output}"
        )
    return output


def _slug(text: str, max_len: int = 40) -> str:
    """Convert text to a git-safe slug."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text[:max_len].rstrip("-")


def _inject_token(repo_url: str, token: str) -> str:
    """Turn https://github.com/owner/repo into https://{token}@github.com/owner/repo"""
    parsed = urlparse(repo_url)
    return parsed._replace(netloc=f"{token}@{parsed.netloc}").geturl()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_workspace(workspace_name: str, repo_url: str, repo_name: str) -> Path:
    """
    Clone the repo into {WORKSPACES_BASE}/{workspace_name}/{repo_name}/ if not present,
    otherwise fetch + reset to the default remote HEAD.
    Configures local git identity.
    Returns the repo path.
    """
    workspace_dir = Path(WORKSPACES_BASE) / workspace_name
    workspace_dir.mkdir(parents=True, exist_ok=True)
    repo_path = workspace_dir / repo_name

    auth_url = _inject_token(repo_url, DEV_GITHUB_TOKEN) if DEV_GITHUB_TOKEN else repo_url

    if not (repo_path / ".git").exists():
        logger.info("Cloning %s into %s", repo_url, repo_path)
        _run(["git", "clone", auth_url, str(repo_path)], cwd=workspace_dir)
    else:
        logger.info("Repo exists at %s — fetching", repo_path)
        # update the remote URL in case token changed
        _run(["git", "remote", "set-url", "origin", auth_url], cwd=repo_path)
        _run(["git", "fetch", "origin"], cwd=repo_path)
        # Reset to remote default branch
        default_branch = _get_default_branch(repo_path)
        _run(["git", "checkout", default_branch], cwd=repo_path)
        _run(["git", "reset", "--hard", f"origin/{default_branch}"], cwd=repo_path)

    # Configure git identity locally
    _run(["git", "config", "user.name", DEV_GIT_NAME], cwd=repo_path)
    _run(["git", "config", "user.email", DEV_GIT_EMAIL], cwd=repo_path)

    return repo_path


def _get_default_branch(repo_path: Path) -> str:
    try:
        out = _run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"], cwd=repo_path
        )
        # refs/remotes/origin/main  → main
        return out.strip().split("/")[-1]
    except RuntimeError:
        return "main"


def create_branch(repo_path: Path, task_id: int, task_title: str) -> str:
    """Create and checkout a new branch task-{id}-{slug}. Returns branch name."""
    branch = f"task-{task_id}-{_slug(task_title)}"
    _run(["git", "checkout", "-b", branch], cwd=repo_path)
    return branch


def run_claude_code(repo_path: Path, claude_prompt: str) -> str:
    """
    Invoke `claude --print` with the pre-generated prompt.
    Returns the combined stdout/stderr output.
    Raises RuntimeError on non-zero exit.
    """
    logger.info("Running claude --print in %s", repo_path)
    result = subprocess.run(
        [
            "claude",
            "--print",
            claude_prompt,
            "--allowedTools",
            "Edit,Write,Read,Bash,Glob,Grep",
        ],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(
            f"claude exited with rc={result.returncode}:\n{output}"
        )
    return output


def push_branch(repo_path: Path, branch: str) -> None:
    """
    Safety-commit anything Claude left uncommitted, then push the branch.
    Injects DEV_GITHUB_TOKEN into the remote URL.
    """
    # Safety catch-all: commit any straggler changes
    status_out = _run(["git", "status", "--porcelain"], cwd=repo_path)
    if status_out.strip():
        logger.info("Safety commit: uncommitted changes found after claude run")
        _run(["git", "add", "-A"], cwd=repo_path)
        _run(
            ["git", "commit", "-m", "chore: apply remaining changes"],
            cwd=repo_path,
        )

    _run(["git", "push", "origin", branch], cwd=repo_path)
    logger.info("Pushed branch %s", branch)


def open_pull_request(
    repo_full_name: str,
    branch: str,
    title: str,
    description: str,
    task_id: int,
) -> str:
    """
    Create a GitHub PR. Returns the PR HTML URL.
    repo_full_name: "owner/repo"
    """
    if not DEV_GITHUB_TOKEN:
        raise RuntimeError("DEV_GITHUB_TOKEN is not set")

    base_branch = "main"
    body = f"{description}\n\n---\n*Automated PR for task #{task_id}*"

    resp = requests.post(
        f"https://api.github.com/repos/{repo_full_name}/pulls",
        headers={
            "Authorization": f"token {DEV_GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "title": title,
            "body": body,
            "head": branch,
            "base": base_branch,
        },
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"GitHub PR creation failed ({resp.status_code}): {resp.text}"
        )
    return resp.json()["html_url"]


def close_pull_request(pr_url: str, reason: str = "") -> None:
    """
    Close a GitHub PR without merging it.
    pr_url is the HTML URL, e.g. https://github.com/owner/repo/pull/42
    """
    if not DEV_GITHUB_TOKEN:
        raise RuntimeError("DEV_GITHUB_TOKEN is not set")

    # Parse owner/repo/pull_number from the HTML URL
    parsed = urlparse(pr_url.rstrip("/"))
    parts = parsed.path.strip("/").split("/")
    # parts: ["owner", "repo", "pull", "42"]
    if len(parts) < 4 or parts[2] != "pull":
        raise ValueError(f"Cannot parse PR URL: {pr_url}")
    owner, repo, pull_number = parts[0], parts[1], parts[3]

    body = {"state": "closed"}
    resp = requests.patch(
        f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}",
        headers={
            "Authorization": f"token {DEV_GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json=body,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"GitHub PR close failed ({resp.status_code}): {resp.text}"
        )

    # Optionally post a comment explaining why
    if reason:
        requests.post(
            f"https://api.github.com/repos/{owner}/{repo}/issues/{pull_number}/comments",
            headers={
                "Authorization": f"token {DEV_GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json",
            },
            json={"body": f"Closing: {reason}"},
            timeout=30,
        )

    logger.info("Closed PR %s", pr_url)


def extract_repo_info(github_repo_url: str) -> tuple[str, str]:
    """
    Parse a GitHub URL and return (full_name, repo_name).
    e.g. "https://github.com/owner/my-repo" → ("owner/my-repo", "my-repo")
    """
    parsed = urlparse(github_repo_url.rstrip("/"))
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse GitHub repo URL: {github_repo_url}")
    full_name = f"{parts[0]}/{parts[1]}"
    repo_name = parts[1]
    return full_name, repo_name
