import json
import logging

from celery import shared_task

from team.agents.team_lead import extract_tasks

logger = logging.getLogger(__name__)

TECH_SPEC_MARKERS = ["## Overview", "## Architecture"]


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_chat_message(self, project_id: int, assistant_message_id: int):
    from .agents.team_lead import run_tech_lead_with_history
    from .models import Message, Project, TechSpec

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

        response_text = run_tech_lead_with_history(history, new_user_message)

        assistant_msg.content = response_text
        assistant_msg.processing = False
        assistant_msg.save()

        if project.status == Project.STATUS_DRAFT:
            # keep off planning
            project.status = Project.STATUS_PLANNING
            project.save(update_fields=["status"])

        _maybe_update_tech_spec(project, response_text)

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


def _maybe_update_tech_spec(project, response_text: str):
    from .models import TechSpec

    has_spec = any(marker in response_text for marker in TECH_SPEC_MARKERS)
    if not has_spec:
        return

    try:
        tech_spec = project.tech_spec
        tech_spec.content = response_text
        tech_spec.version += 1
        tech_spec.save()
    except TechSpec.DoesNotExist:
        TechSpec.objects.create(
            project=project, content=response_text, version=1
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def generate_dev_tasks(self, project_id: int):
    from agno.agent import Agent
    from agno.models.anthropic import Claude

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

        project.status = Project.STATUS_IN_PROGRESS
        project.save(update_fields=["status"])

    except Exception as exc:
        logger.exception(
            "Error generating dev tasks for project %s", project_id
        )
        raise self.retry(exc=exc)
