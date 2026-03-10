import logging

from celery import shared_task

from team.agents.team_lead import extract_tasks

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_chat_message(self, project_id: int, assistant_message_id: int):
    from .agents.team_lead import run_tech_lead_with_history
    from .models import Message, Project

    try:
        project = Project.objects.get(id=project_id)
        assistant_msg = Message.objects.get(id=assistant_message_id)
        conversation = project.conversation

        all_messages = list(
            conversation.messages.exclude(id=assistant_message_id).order_by(
                "created_at"
            )
        )

        if not all_messages:
            assistant_msg.content = "No messages found to process."
            assistant_msg.processing = False
            assistant_msg.save()
            return

        history = [
            {"role": m.role, "content": m.content} for m in all_messages[:-1]
        ]
        new_user_message = all_messages[-1].content

        response_text = run_tech_lead_with_history(
            project_id, history, new_user_message
        )

        assistant_msg.content = response_text
        assistant_msg.processing = False
        assistant_msg.save()

        if project.status == Project.STATUS_DRAFT:
            project.status = Project.STATUS_PLANNING
            project.save(update_fields=["status"])

    except Exception as exc:
        logger.exception(
            "Error processing chat message %s", assistant_message_id
        )
        try:
            msg = Message.objects.get(id=assistant_message_id)
            msg.content = f"Error: {exc}"
            msg.processing = False
            msg.save()
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def generate_dev_tasks(self, project_id: int):
    from .models import DevTask, Project

    try:
        project = Project.objects.get(id=project_id)
        tech_spec = project.tech_spec
        task_data = extract_tasks(tech_spec.content)

        # Pass 1: create all tasks
        created_tasks = {}
        for idx, item in enumerate(task_data):
            task = DevTask.objects.create(
                project=project,
                title=item["title"],
                description=item.get("description", ""),
                priority=item.get("priority", 3),
                order=idx,
                claude_prompt=item.get("claude_prompt", ""),
            )
            created_tasks[item["title"]] = task

        # Pass 2: wire blocked_by M2M
        for item in task_data:
            task = created_tasks.get(item["title"])
            if task and item.get("blocked_by"):
                for blocker_title in item["blocked_by"]:
                    blocker = created_tasks.get(blocker_title)
                    if blocker:
                        task.blocked_by.add(blocker)

    except Exception as exc:
        logger.exception(
            "Error generating dev tasks for project %s", project_id
        )
        raise self.retry(exc=exc)


@shared_task
def run_dev_task(task_id: int):
    from django.db import transaction

    from .agents.dev_agent import (
        branch_name,
        extract_repo_info,
        run_claude_agent,
        setup_workspace,
    )
    from .models import DevTask, Workspace

    task = DevTask.objects.get(id=task_id)
    workspace = None

    def _log(msg: str):
        task.agent_log += msg + "\n"
        task.save(update_fields=["agent_log"])
        logger.info("[task-%d] %s", task_id, msg)

    try:
        if task.blocked_by.exclude(
            status__in=[DevTask.STATUS_DONE, DevTask.STATUS_ABORTED]
        ).exists():
            _log(
                "Task has dependencies that are not done — task will run on next trigger."
            )
            return

        # Claim an available workspace atomically
        with transaction.atomic():
            workspace = (
                Workspace.objects.select_for_update(skip_locked=True)
                .filter(current_task=None)
                .first()
            )
            if not workspace:
                _log("No available workspace — task will run on next trigger.")
                return
            workspace.claim(task)

        _log(f"Claimed workspace: {workspace.name}")

        repo_url = task.project.github_repo_url
        if not repo_url:
            raise ValueError(
                f"Project {task.project_id} has no github_repo_url"
            )

        _, repo_name = extract_repo_info(repo_url)
        branch = branch_name(task_id, task.title)

        task.branch_name = branch
        task.status = DevTask.STATUS_IN_PROGRESS
        task.save(update_fields=["branch_name", "status"])

        _log("Setting up workspace")
        repo_path = setup_workspace(workspace.name, repo_url, repo_name)

        _log("Running claude agent")

        def _stream(line: str):
            task.agent_log += line + "\n"
            task.save(update_fields=["agent_log"])
            logger.info("[task-%d] %s", task_id, line)

        pr_url = run_claude_agent(
            repo_path,
            branch,
            task.title,
            task.description,
            task.claude_prompt,
            on_output=_stream,
        )

        task.pr_url = pr_url
        task.status = DevTask.STATUS_PR_OPEN
        task.save(update_fields=["pr_url", "status"])
        _log(f"PR opened: {pr_url}")

    except Exception as exc:
        logger.exception("run_dev_task failed for task %s", task_id)
        task.agent_log += f"\nFAILED: {exc}\n"
        task.status = DevTask.STATUS_PENDING
        task.save(update_fields=["agent_log", "status"])

    finally:
        if workspace is not None:
            workspace.release()


@shared_task
def cleanup_workspace_branch(task_id: int):
    """
    After a PR is merged, find every workspace that has this task's repo cloned
    and clean up the local branch: switch to main, pull latest, delete branch.
    """
    from pathlib import Path

    from .agents.dev_agent import (
        WORKSPACES_BASE,
        cleanup_merged_branch,
        extract_repo_info,
    )
    from .models import DevTask

    try:
        task = DevTask.objects.select_related("project").get(id=task_id)
    except DevTask.DoesNotExist:
        return

    if not task.branch_name or not task.project.github_repo_url:
        return

    _, repo_name = extract_repo_info(task.project.github_repo_url)
    workspaces_root = Path(WORKSPACES_BASE)

    if not workspaces_root.exists():
        return

    for ws_dir in workspaces_root.iterdir():
        if not ws_dir.is_dir():
            continue
        repo_path = ws_dir / repo_name
        if (repo_path / ".git").exists():
            try:
                cleanup_merged_branch(repo_path, task.branch_name)
                logger.info(
                    "Cleaned up branch %s in workspace %s",
                    task.branch_name,
                    ws_dir.name,
                )
            except Exception:
                logger.exception(
                    "Failed to cleanup branch %s in workspace %s",
                    task.branch_name,
                    ws_dir.name,
                )


@shared_task
def project_manager_assign():
    from .models import DevTask, Project, Workspace

    tasks = (
        DevTask.objects.filter(
            status=DevTask.STATUS_PENDING,
            project__status=Project.STATUS_IN_PROGRESS,
        )
        .exclude(
            blocked_by__status__in=[
                s
                for s, _ in DevTask.STATUS_CHOICES
                if s not in (DevTask.STATUS_DONE, DevTask.STATUS_ABORTED)
            ]
        )
        .order_by("project", "order", "priority")
    )

    available_count = Workspace.objects.filter(current_task=None).count()
    tasks_to_queue = tasks[:available_count]

    for task in tasks_to_queue:
        run_dev_task.delay(task.id)
        logger.info("Queued task %s (%s)", task.id, task.title)

    logger.info(
        "project_manager_assign: queued %d/%d tasks (%d workspaces available)",
        len(tasks_to_queue),
        tasks.count(),
        available_count,
    )
