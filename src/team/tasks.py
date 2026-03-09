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
        create_branch,
        extract_repo_info,
        open_pull_request,
        push_branch,
        run_claude_code,
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
        if task.depends_on.exclude(
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

        repo_full_name, repo_name = extract_repo_info(repo_url)

        _log("Setting up workspace")
        repo_path = setup_workspace(workspace.name, repo_url, repo_name)

        _log("Creating branch")
        branch = create_branch(repo_path, task_id, task.title)
        task.branch_name = branch
        task.status = DevTask.STATUS_IN_PROGRESS
        task.save(update_fields=["branch_name", "status"])

        _log("Running claude --print")
        claude_output = run_claude_code(repo_path, task.claude_prompt)
        _log(claude_output[:4000])

        _log("Pushing branch")
        push_branch(repo_path, branch)

        _log("Opening pull request")
        pr_url = open_pull_request(
            repo_full_name, branch, task.title, task.description, task_id
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
