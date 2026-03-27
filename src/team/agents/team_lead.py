import json
import logging
import time

from anthropic import Anthropic

from .utils.helpers import compute_cost

logger = logging.getLogger(__name__)

TECH_LEAD_MODEL = "claude-opus-4-6"
CLIENT = Anthropic()
MAX_TOKENS = 16000


# ---------------------------------------------------------------------------
# Dynamic system prompt — includes live project context
# ---------------------------------------------------------------------------


def _build_system_prompt(project) -> str:
    return f"""You are a senior Tech Lead embedded in an AI-powered developer team.

**Project:** {project.name} (ID: {project.id}, status: `{project.status}`)

You collaborate with the user across the full project lifecycle — from initial scoping all the way through active development. You have tools to read and directly manage the project's tasks and tech spec.

---

## Phase: Initial Planning
When there is no tech spec yet:
1. Ask ONE focused clarifying question at a time to understand requirements.
2. When you have enough information, produce a comprehensive TechSpec using the format below.
3. Immediately call `update_tech_spec` with the full spec content.
4. Then call `upsert_task` once per task to create the development backlog.
5. **Do NOT set the project status to `approved` or `in_progress` automatically.** After presenting the spec, simply ask the user if they'd like any changes. The user must explicitly ask you to start the project before you call `update_project_status`.

## Phase: Ongoing Collaboration
When the project already has a spec or is in progress:
1. Before responding to change requests, call `list_tasks` to review current state.
2. For scope changes to existing work: call `upsert_task` with the relevant `task_id`.
3. For new requirements: call `upsert_task` without `task_id` to add new tasks.
4. **Never modify tasks with status `in_progress`, `pr_open`, or `done`** — those are immutable.
5. When a task is no longer needed (superseded by a change request, scope reduction, etc.), call `abort_task` — this closes the PR on GitHub if one exists and marks the task aborted.
6. If the architecture changes materially, call `update_tech_spec` with the revised spec.
7. Be transparent: tell the user exactly which tasks you changed, created, or aborted and why.

---

## TechSpec Format
Always use this exact structure when creating or updating a TechSpec:

## Overview
[Brief description of the feature]

## Goals & Non-Goals
[What this feature will and won't do]

## Architecture
[High-level architecture decisions]

## Data Models
[Database models and their fields]

## API Endpoints
[API endpoints with methods and descriptions]

## Key Workflows
[Step-by-step description of key user flows]

## Implementation Plan
[Ordered list of implementation steps]

## Open Questions
[Any remaining uncertainties]

---

## Task Field Guidelines
- `title`: short, human-readable (≤ 10 words)
- `description`: 1-3 sentences for human context only
- `claude_prompt`: detailed markdown prompt for Claude Code — include exact file paths, data model details, API contracts, expected behaviour, and always end with: "Stage and commit all changes when done."
- `priority`: 1 (highest) to 5 (lowest)
- `blocked_by_ids`: list of task IDs this task depends on (empty list if none)
"""


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_tasks",
        "description": (
            "List all development tasks for this project. "
            "Returns each task's id, title, status, priority, order, and blocked_by task IDs. "
            "Call this before making any changes during ongoing collaboration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "upsert_task",
        "description": (
            "Create a new dev task or update an existing pending one. "
            "Pass `task_id` to update; omit it to create a new task. "
            "Cannot modify tasks whose status is in_progress, pr_open, or done."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "ID of an existing task to update. Omit to create a new task.",
                },
                "title": {
                    "type": "string",
                    "description": "Short human-readable task title (≤ 10 words).",
                },
                "description": {
                    "type": "string",
                    "description": "Brief human-readable description (1-3 sentences).",
                },
                "claude_prompt": {
                    "type": "string",
                    "description": (
                        "Detailed markdown implementation prompt for Claude Code. "
                        "Include file paths, data models, API contracts, exact behaviour, "
                        "and end with a commit instruction."
                    ),
                },
                "priority": {
                    "type": "integer",
                    "description": "1 = highest priority, 5 = lowest.",
                },
                "blocked_by_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "IDs of tasks that must complete before this one starts.",
                },
            },
            "required": ["title", "description", "claude_prompt", "priority"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_tech_spec",
        "description": (
            "Replace the project's tech spec with updated content. "
            "Use the prescribed TechSpec markdown format. "
            "Call this whenever the architecture or requirements change materially."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Full updated tech spec in markdown format.",
                },
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "abort_task",
        "description": (
            "Mark a task as aborted when it is no longer needed or has been superseded. "
            "If the task has an open PR, it will be closed on GitHub automatically. "
            "Cannot abort tasks that are already done."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "ID of the task to abort.",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why the task is being aborted. Posted as a PR comment if a PR exists.",
                },
            },
            "required": ["task_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_project_status",
        "description": "Update the project's status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [
                        "draft",
                        "planning",
                        "approved",
                        "in_progress",
                        "aborted",
                        "completed",
                    ],
                },
            },
            "required": ["status"],
            "additionalProperties": False,
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution — all DB access via lazy imports
# ---------------------------------------------------------------------------


def _execute_tool(name: str, tool_input: dict, project_id: int) -> str:
    from team.models import DevTask, Project, TechSpec

    if name == "list_tasks":
        tasks = (
            DevTask.objects.filter(project_id=project_id)
            .prefetch_related("blocked_by")
            .order_by("order", "priority")
        )
        return json.dumps(
            [
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "order": t.order,
                    "blocked_by": [b.id for b in t.blocked_by.all()],
                }
                for t in tasks
            ]
        )

    if name == "upsert_task":
        task_id = tool_input.get("task_id")
        if task_id:
            try:
                task = DevTask.objects.get(id=task_id, project_id=project_id)
            except DevTask.DoesNotExist:
                return json.dumps(
                    {"error": f"Task {task_id} not found in this project."}
                )
            if task.status != DevTask.STATUS_PENDING:
                return json.dumps(
                    {
                        "error": f"Cannot modify task {task_id} — status is '{task.status}'."
                    }
                )
            for field in ("title", "description", "claude_prompt", "priority"):
                if field in tool_input:
                    setattr(task, field, tool_input[field])
            task.save()
        else:
            order = DevTask.objects.filter(project_id=project_id).count()
            task = DevTask.objects.create(
                project_id=project_id,
                title=tool_input["title"],
                description=tool_input["description"],
                claude_prompt=tool_input.get("claude_prompt", ""),
                priority=tool_input.get("priority", 3),
                order=order,
            )
        if "blocked_by_ids" in tool_input:
            blockers = DevTask.objects.filter(
                id__in=tool_input["blocked_by_ids"], project_id=project_id
            )
            task.blocked_by.set(blockers)
        return json.dumps(
            {"id": task.id, "title": task.title, "status": task.status}
        )

    if name == "abort_task":
        from .dev_agent import close_pull_request

        try:
            task = DevTask.objects.get(
                id=tool_input["task_id"], project_id=project_id
            )
        except DevTask.DoesNotExist:
            return json.dumps(
                {"error": f"Task {tool_input['task_id']} not found."}
            )
        if task.status == DevTask.STATUS_DONE:
            return json.dumps({"error": "Cannot abort a completed task."})
        if task.status == DevTask.STATUS_ABORTED:
            return json.dumps({"error": "Task is already aborted."})

        reason = tool_input.get("reason", "")
        if task.pr_url:
            try:
                close_pull_request(task.pr_url, reason=reason)
            except Exception as exc:
                logger.warning("Could not close PR %s: %s", task.pr_url, exc)

        task.status = DevTask.STATUS_ABORTED
        task.save(update_fields=["status"])
        return json.dumps(
            {"id": task.id, "title": task.title, "status": task.status}
        )

    if name == "update_tech_spec":
        content = tool_input["content"]
        try:
            spec = TechSpec.objects.get(project_id=project_id)
            spec.content = content
            spec.version += 1
            spec.save()
        except TechSpec.DoesNotExist:
            TechSpec.objects.create(
                project_id=project_id, content=content, version=1
            )
        return json.dumps({"success": True})

    if name == "update_project_status":
        status = tool_input["status"]
        project = Project.objects.get(id=project_id)
        github_error = None
        if status == "in_progress" and not project.github_repo_url:
            from ..github import upsert_github_repo

            try:
                tech_spec_content = ""
                try:
                    spec = TechSpec.objects.get(project_id=project_id)
                    tech_spec_content = spec.content
                except TechSpec.DoesNotExist:
                    pass
                project.github_repo_url = upsert_github_repo(
                    project.name,
                    project.description,
                    readme_content=tech_spec_content,
                )
                project.status = status
                project.save(update_fields=["status", "github_repo_url"])
            except Exception as exc:
                github_error = str(exc)
                logger.warning(
                    "Could not upsert GitHub repo for project %s: %s",
                    project_id,
                    exc,
                )
                Project.objects.filter(id=project_id).update(status=status)
        else:
            Project.objects.filter(id=project_id).update(status=status)
        result = {"success": True, "status": status}
        if github_error:
            result["github_error"] = github_error
        elif status == "in_progress":
            result["github_repo_url"] = project.github_repo_url
        return json.dumps(result)

    return json.dumps({"error": f"Unknown tool: {name}"})


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_tech_lead_with_history(
    project_id: int, history: list[dict], new_user_message: str
) -> dict:
    """
    Run the agentic tech lead loop for one user turn.
    Executes tool calls against the DB in a loop until the model stops.

    Returns:
        {
            "response": str,
            "token_cost": Decimal,
            "response_time_ms": int,
        }
    """
    from team.models import Project

    project = Project.objects.get(id=project_id)
    system = _build_system_prompt(project)

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": new_user_message})

    total_input_tokens = 0
    total_output_tokens = 0
    start = time.monotonic()

    response = None
    while True:
        with CLIENT.messages.stream(
            model=TECH_LEAD_MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            system=system,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                logger.info(
                    "Tech lead calling tool: %s %s", block.name, block.input
                )
                try:
                    result = _execute_tool(block.name, block.input, project_id)
                except Exception as exc:
                    logger.exception("Tool %s raised an exception", block.name)
                    result = json.dumps({"error": str(exc)})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

        messages.append({"role": "user", "content": tool_results})

    elapsed_ms = int((time.monotonic() - start) * 1000)
    cost = compute_cost(
        TECH_LEAD_MODEL, total_input_tokens, total_output_tokens
    )

    logger.info(
        "Tech lead turn: %d input + %d output tokens, cost=$%s, %dms",
        total_input_tokens,
        total_output_tokens,
        cost,
        elapsed_ms,
    )

    text_blocks = [b.text for b in response.content if b.type == "text"]
    return {
        "response": "\n".join(text_blocks),
        "token_cost": cost,
        "response_time_ms": elapsed_ms,
    }


# ---------------------------------------------------------------------------
# Utility functions (used by generate_dev_tasks and API)
# ---------------------------------------------------------------------------

TASK_EXTRACTION_PROMPT = """You are given a TechSpec document. Extract the development tasks from it.

Return ONLY a JSON array with no other text, no markdown code blocks, just raw JSON.

Each task object must have:
- "title": string (short task title, human-readable)
- "description": string (brief human-readable description, 1-3 sentences)
- "priority": integer (1=highest, 5=lowest)
- "blocked_by": array of strings (titles of tasks this task depends on, empty array if none)
- "claude_prompt": string (detailed markdown implementation prompt for Claude Code — include full context from the TechSpec needed to implement this specific task: relevant data models, API contracts, file paths to create/edit, exact behaviour expected, and a final instruction to commit all changes)

Example:
[
  {{
    "title": "Set up database models",
    "description": "Create the core data models for the feature.",
    "priority": 1,
    "blocked_by": [],
    "claude_prompt": "## Task: Set up database models\\n\\n### Context\\n...tech spec excerpt...\\n\\n### What to implement\\n1. Create `MyModel` in `app/models.py` with fields: ...\\n2. Write and run the migration.\\n\\n### Commit\\nWhen done, stage and commit all changes with message: `feat: add database models`"
  }}
]

TechSpec:
{spec_content}"""

PROJECT_EXTRACTION_PROMPT = """
You are given an idea for a software project. Extract the project name and formatted description from it.

Respond with ONLY a raw JSON object — no markdown, no code blocks.

Example:
{{"name": "Project Name", "description": "Project Description"}}

Idea: {idea}
"""


def extract_project_info(idea: str) -> dict:
    response = CLIENT.messages.create(
        model=TECH_LEAD_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": PROJECT_EXTRACTION_PROMPT.format(idea=idea),
            }
        ],
    )
    return json.loads(response.content[0].text.strip())


def extract_tasks(tech_spec: str) -> list[dict]:
    response = CLIENT.messages.create(
        model=TECH_LEAD_MODEL,
        max_tokens=MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": TASK_EXTRACTION_PROMPT.format(
                    spec_content=tech_spec
                ),
            }
        ],
    )
    return json.loads(response.content[0].text.strip())
