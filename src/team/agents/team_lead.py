import json
import logging
import time

from anthropic import Anthropic

from .utils.helpers import compute_cost

logger = logging.getLogger(__name__)

TECH_LEAD_MODEL = "claude-opus-4-6"
CLIENT = Anthropic()
MAX_TOKENS = 8000


# ---------------------------------------------------------------------------
# Dynamic system prompt — includes live project context
# ---------------------------------------------------------------------------


def _build_system_prompt(project) -> str:
    return f"""You are a Tech Lead in an AI dev team.

Project: {project.name} (ID: {project.id}, status: `{project.status}`)

## Step 1 — Write TechSpec (no tasks yet)
1. Ask ONE clarifying question at a time.
2. When ready, call `update_tech_spec` with a concise spec (format below).
3. Present the spec and ask user for feedback. STOP HERE.
4. Do NOT call `upsert_task` or `update_project_status` during this step.

## Step 2 — Create Tasks (only after user approves the spec)
Only when the user explicitly approves/accepts the spec:
1. Call `replace_all_tasks` with the full task list (this deletes any old pending tasks first).
2. Do NOT set status to `approved`/`in_progress` — ask user first.

## Ongoing Changes (after initial tasks are created)
When the user requests changes — whether tasks are still pending, in progress, or all finished:
1. Always call `list_tasks` first to see current task statuses.
2. Understand what the user wants changed and map it to existing or new tasks.
3. If a change overlaps with an existing **pending** task, update that task via `upsert_task` with its `task_id` — do NOT create a duplicate.
4. If all tasks are finished (`done`/`aborted`) and the user requests new work, create new tasks via `upsert_task` (individual) or `replace_all_tasks` (batch). These are added alongside completed tasks.
5. To wholesale replace all remaining pending tasks, use `replace_all_tasks`.
6. Never modify tasks with status `in_progress`/`pr_open`/`done`.
7. Use `abort_task` for scope that's been removed. Tell user what changed and why.
8. Use `delete_task` to permanently remove pending or aborted tasks (e.g. obsolete leftovers).
9. Call `update_tech_spec` only if architecture changes materially.

## TechSpec Format (concise — no exhaustive field/endpoint listings)

## Overview
One paragraph: what and why.

## Goals & Non-Goals
Bullet list, max 5 each.

## Architecture
Key decisions only: stack choices, component relationships, data flow. Name models/tables but do NOT list every field — dev tasks will specify details.

## Implementation Plan
Ordered steps mapping to tasks.

## Open Questions
Only if any remain.

## Task Guidelines
- `title`: ≤10 words
- `description`: 1-2 sentences
- `claude_prompt`: focused implementation instructions — what to build, key file paths, end with "Stage and commit all changes when done." Reference the tech spec rather than repeating it.
- `priority`: 1-5
- `blocked_by_ids`: dependency task IDs
"""


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_tasks",
        "description": "List all tasks (id, title, description, status, priority, order, blocked_by).",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "upsert_task",
        "description": "Create or update a pending dev task. Pass task_id to update, omit to create.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "Existing task ID to update. Omit to create.",
                },
                "title": {
                    "type": "string",
                    "description": "Task title (≤10 words).",
                },
                "description": {
                    "type": "string",
                    "description": "1-2 sentence summary.",
                },
                "claude_prompt": {
                    "type": "string",
                    "description": "Implementation prompt for Claude Code. End with commit instruction.",
                },
                "priority": {
                    "type": "integer",
                    "description": "1=highest, 5=lowest.",
                },
                "blocked_by_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Task IDs this depends on.",
                },
            },
            "required": ["title", "description", "claude_prompt", "priority"],
            "additionalProperties": False,
        },
    },
    {
        "name": "update_tech_spec",
        "description": "Replace the project's tech spec (markdown).",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Full tech spec markdown.",
                },
            },
            "required": ["content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "replace_all_tasks",
        "description": "Delete all pending tasks and create a new task list. Non-pending tasks are kept.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "description": "New task list to replace pending tasks.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "claude_prompt": {"type": "string"},
                            "priority": {"type": "integer"},
                        },
                        "required": [
                            "title",
                            "description",
                            "claude_prompt",
                            "priority",
                        ],
                    },
                },
            },
            "required": ["tasks"],
            "additionalProperties": False,
        },
    },
    {
        "name": "abort_task",
        "description": "Abort a task (closes PR if any). Cannot abort done tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "Task ID."},
                "reason": {"type": "string", "description": "Why."},
            },
            "required": ["task_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "delete_task",
        "description": "Permanently delete a pending or aborted task. Cannot delete in_progress/pr_open/done tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "Task ID to delete.",
                },
            },
            "required": ["task_id"],
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
                    "description": t.description,
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

    if name == "replace_all_tasks":
        from .dev_agent import close_pull_request

        pending = DevTask.objects.filter(
            project_id=project_id, status=DevTask.STATUS_PENDING
        )
        aborted_ids = []
        for t in pending:
            if t.pr_url:
                try:
                    close_pull_request(
                        t.pr_url, reason="Replaced by new task list"
                    )
                except Exception as exc:
                    logger.warning("Could not close PR %s: %s", t.pr_url, exc)
            aborted_ids.append(t.id)
        pending.delete()

        kept = DevTask.objects.filter(project_id=project_id).exclude(
            status=DevTask.STATUS_PENDING
        )
        start_order = kept.count()

        created = []
        for idx, item in enumerate(tool_input["tasks"]):
            task = DevTask.objects.create(
                project_id=project_id,
                title=item["title"],
                description=item.get("description", ""),
                claude_prompt=item.get("claude_prompt", ""),
                priority=item.get("priority", 3),
                order=start_order + idx,
            )
            created.append({"id": task.id, "title": task.title})
        return json.dumps({"deleted_pending": aborted_ids, "created": created})

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

    if name == "delete_task":
        try:
            task = DevTask.objects.get(
                id=tool_input["task_id"], project_id=project_id
            )
        except DevTask.DoesNotExist:
            return json.dumps(
                {"error": f"Task {tool_input['task_id']} not found."}
            )
        if task.status not in (DevTask.STATUS_PENDING, DevTask.STATUS_ABORTED):
            return json.dumps(
                {
                    "error": f"Cannot delete task {task.id} — status is '{task.status}'. Only pending or aborted tasks can be deleted."
                }
            )
        task_id, task_title = task.id, task.title
        task.delete()
        return json.dumps({"deleted": True, "id": task_id, "title": task_title})

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

TASK_EXTRACTION_PROMPT = """Extract development tasks from this TechSpec. Return ONLY a raw JSON array.

Each task: {{"title": "≤10 words", "description": "1-2 sentences", "priority": 1-5, "blocked_by": ["task titles"], "claude_prompt": "focused implementation instructions — what to build, key files, commit instruction. Do NOT repeat the full spec."}}

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
