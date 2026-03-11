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

logger = logging.getLogger(__name__)

WORKSPACES_BASE = os.environ.get("WORKSPACES_BASE", "/workspaces")
DEV_GITHUB_TOKEN = os.environ.get("DEV_GITHUB_TOKEN", "")
DEV_GIT_NAME = os.environ.get("DEV_GIT_NAME", "Dev Agent")
DEV_GIT_EMAIL = os.environ.get("DEV_GIT_EMAIL", "dev-agent@localhost")

_SKILLS_DIR = Path(__file__).parent / "skills"
_DEV_TASK_SKILL = _SKILLS_DIR / "DEV_TASK_SKILL.md"
_PR_COMMENT_SKILL = _SKILLS_DIR / "PR_COMMENT_SKILL.md"


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


def _get_default_branch(repo_path: Path) -> str:
    try:
        out = _run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"], cwd=repo_path
        )
        return out.strip().split("/")[-1]
    except RuntimeError:
        return "main"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_repo_info(github_repo_url: str) -> tuple[str, str]:
    """
    Parse a GitHub URL and return (full_name, repo_name).
    e.g. "https://github.com/owner/my-repo" → ("owner/my-repo", "my-repo")
    """
    parsed = urlparse(github_repo_url.rstrip("/"))
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse GitHub repo URL: {github_repo_url}")
    return f"{parts[0]}/{parts[1]}", parts[1]


def branch_name(task_id: int, task_title: str) -> str:
    return f"task-{task_id}-{_slug(task_title)}"


def setup_workspace(workspace_name: str, repo_url: str, repo_name: str) -> Path:
    """
    Clone the repo into {WORKSPACES_BASE}/{workspace_name}/{repo_name}/ if not present,
    otherwise fetch + reset to the default remote HEAD.
    Configures local git identity and injects gh auth via GH_TOKEN env.
    Returns the repo path.
    """
    workspace_dir = Path(WORKSPACES_BASE) / workspace_name
    workspace_dir.mkdir(parents=True, exist_ok=True)
    repo_path = workspace_dir / repo_name

    auth_url = (
        _inject_token(repo_url, DEV_GITHUB_TOKEN)
        if DEV_GITHUB_TOKEN
        else repo_url
    )

    if not (repo_path / ".git").exists():
        logger.info("Cloning %s into %s", repo_url, repo_path)
        _run(["git", "clone", auth_url, str(repo_path)], cwd=workspace_dir)
    else:
        logger.info("Repo exists at %s — fetching", repo_path)
        _run(["git", "remote", "set-url", "origin", auth_url], cwd=repo_path)
        # --prune removes stale remote-tracking refs that cause "cannot lock ref" errors
        try:
            _run(["git", "fetch", "--prune", "origin"], cwd=repo_path)
        except RuntimeError:
            # Corrupt ref state — nuke the packed-refs cache and retry
            logger.warning("git fetch --prune failed in %s, clearing packed-refs and retrying", repo_path)
            packed_refs = repo_path / ".git" / "packed-refs"
            if packed_refs.exists():
                packed_refs.unlink()
            _run(["git", "fetch", "--prune", "origin"], cwd=repo_path)
        default = _get_default_branch(repo_path)
        _run(["git", "checkout", default], cwd=repo_path)
        _run(["git", "reset", "--hard", f"origin/{default}"], cwd=repo_path)

    _run(["git", "config", "user.name", DEV_GIT_NAME], cwd=repo_path)
    _run(["git", "config", "user.email", DEV_GIT_EMAIL], cwd=repo_path)

    return repo_path


def run_claude_agent(
    repo_path: Path,
    branch: str,
    task_title: str,
    task_description: str,
    claude_prompt: str,
    on_output: callable = None,
) -> str:
    """
    Write SKILL.md to the repo, then invoke claude --print to handle the full
    branch → implement → commit → push → PR workflow.
    Streams output line-by-line; calls on_output(line) for each line if provided.
    Returns the PR URL parsed from Claude's output.
    """
    (repo_path / "SKILL.md").write_text(_DEV_TASK_SKILL.read_text())

    prompt = (
        f"Follow the instructions in SKILL.md.\n\n"
        f"Branch name: {branch}\n"
        f"Task title: {task_title}\n\n"
        f"## Description\n{task_description}\n\n"
        f"## Implementation Details\n{claude_prompt}"
    )

    env = os.environ.copy()
    if DEV_GITHUB_TOKEN:
        env["GH_TOKEN"] = DEV_GITHUB_TOKEN

    proc = subprocess.Popen(
        [
            "claude",
            "--print",
            prompt,
            "--allowedTools",
            "Edit,Write,Read,Bash,Glob,Grep",
        ],
        cwd=str(repo_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    lines: list[str] = []
    for raw in proc.stdout:
        line = raw.rstrip("\n")
        lines.append(line)
        logger.info("[claude] %s", line)
        if on_output:
            on_output(line)

    proc.wait(timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude exited with rc={proc.returncode}:\n" + "\n".join(lines[-100:])
        )

    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("PR_URL:"):
            return stripped.split("PR_URL:", 1)[1].strip()

    raise RuntimeError(
        f"Could not find PR_URL in claude output:\n" + "\n".join(lines[-100:])
    )


_CHANGE_REQUEST_KEYWORDS = re.compile(
    r"\b(update|apply|fix|change|rename|remove|delete|add|refactor|move|replace|please\s+\w+|can\s+you)\b",
    re.IGNORECASE,
)


def _is_change_request(comment_body: str) -> bool:
    """Heuristic: return True if the comment is likely requesting a code change."""
    return bool(_CHANGE_REQUEST_KEYWORDS.search(comment_body))


def run_claude_agent_for_pr_comment(
    repo_path: Path,
    branch: str,
    pr_url: str,
    comment_body: str,
    commenter: str,
    event_type: str = "comment",
    comment_id: int | None = None,
    repo_full_name: str = "",
    pr_number: int | None = None,
    on_output: callable = None,
) -> None:
    """
    Run Claude Code to handle a PR review comment.

    - Writes PR_COMMENT_SKILL.md to the repo so Claude has workflow instructions.
    - If the comment contains change-request keywords, Claude will implement the
      change, commit, push, then reply in the original thread.
    - Otherwise Claude answers the question in-thread without touching the code.
    - For pull_request_review_comment events the reply goes back into the diff
      thread via the GitHub replies API; other events get a top-level PR comment.
    """
    env = os.environ.copy()
    if DEV_GITHUB_TOKEN:
        env["GH_TOKEN"] = DEV_GITHUB_TOKEN

    # Write the skill guide so Claude can reference it
    (repo_path / "PR_COMMENT_SKILL.md").write_text(_PR_COMMENT_SKILL.read_text())

    # Build the exact reply command for this event type
    if event_type == "review_comment" and comment_id and repo_full_name and pr_number:
        reply_cmd = (
            f"gh api -X POST repos/{repo_full_name}/pulls/{pr_number}"
            f"/comments/{comment_id}/replies -f body='YOUR_REPLY'"
        )
    else:
        reply_cmd = f"gh pr comment {pr_url} --body 'YOUR_REPLY'"

    hint = (
        "The reviewer is **requesting a code change** — follow the Change Path in PR_COMMENT_SKILL.md."
        if _is_change_request(comment_body)
        else "The reviewer appears to be asking a question — follow the Answer Path in PR_COMMENT_SKILL.md."
    )

    prompt = (
        f"Follow the instructions in PR_COMMENT_SKILL.md.\n\n"
        f"PR URL: {pr_url}\n"
        f"Branch: {branch}\n"
        f"Reviewer: @{commenter}\n"
        f"Event type: {event_type}\n\n"
        f"## Reviewer's Comment\n{comment_body}\n\n"
        f"## Reply Command\n"
        f"Use this exact command to post your reply (replace YOUR_REPLY with your message):\n"
        f"`{reply_cmd}`\n\n"
        f"## Hint\n{hint}"
    )

    proc = subprocess.Popen(
        [
            "claude",
            "--print",
            prompt,
            "--allowedTools",
            "Edit,Write,Read,Bash,Glob,Grep",
        ],
        cwd=str(repo_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    for raw in proc.stdout:
        line = raw.rstrip("\n")
        logger.info("[claude-pr-comment] %s", line)
        if on_output:
            on_output(line)

    proc.wait(timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited with rc={proc.returncode}")


def cleanup_merged_branch(repo_path: Path, branch: str) -> None:
    """
    After a PR is merged: switch to main, pull latest, delete the local branch.
    Safe to call even if the branch does not exist locally.
    """
    default = _get_default_branch(repo_path)
    _run(["git", "checkout", default], cwd=repo_path)
    _run(["git", "pull", "origin", default], cwd=repo_path)
    try:
        _run(["git", "branch", "-D", branch], cwd=repo_path)
        logger.info("Deleted local branch %s in %s", branch, repo_path)
    except RuntimeError:
        logger.info(
            "Branch %s not found locally in %s — skipping delete",
            branch,
            repo_path,
        )
