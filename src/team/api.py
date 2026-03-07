from ninja import NinjaAPI
from ninja.errors import HttpError

from .models import Conversation, DevTask, Message, Project
from .schemas import (
    ApproveResponseSchema,
    ChatRequestSchema,
    ChatResponseSchema,
    CreateFromIdeaRequestSchema,
    CreateFromIdeaResponseSchema,
    DevTaskSchema,
    MessageSchema,
    ProjectStatusResponseSchema,
    RunDevAgentsResponseSchema,
    StartProjectResponseSchema,
)

api = NinjaAPI()


def _get_or_create_conversation(project: Project) -> Conversation:
    conversation, _ = Conversation.objects.get_or_create(project=project)
    return conversation


@api.post("/projects/create-from-idea/", response=CreateFromIdeaResponseSchema)
def create_from_idea(request, payload: CreateFromIdeaRequestSchema):
    from .agents.team_lead import extract_project_info
    from .tasks import process_chat_message

    info = extract_project_info(payload.idea)
    project = Project.objects.create(
        name=info["name"],
        description=info.get("description", ""),
        status=Project.STATUS_PLANNING,
    )
    conversation = Conversation.objects.create(project=project)

    user_msg = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_USER,
        content=payload.idea,
    )
    assistant_msg = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_ASSISTANT,
        content="",
        processing=True,
    )

    process_chat_message.delay(project.id, assistant_msg.id)

    return CreateFromIdeaResponseSchema(
        project_id=project.id,
        assistant_message_id=assistant_msg.id,
    )


@api.post("/projects/{project_id}/chat/", response=ChatResponseSchema)
def chat(request, project_id: int, payload: ChatRequestSchema):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    conversation = _get_or_create_conversation(project)

    user_msg = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_USER,
        content=payload.content,
    )

    assistant_msg = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_ASSISTANT,
        content="",
        processing=True,
    )

    from .tasks import process_chat_message

    process_chat_message.delay(project_id, assistant_msg.id)

    return ChatResponseSchema(
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
    )


@api.get("/projects/{project_id}/messages/", response=list[MessageSchema])
def get_messages(request, project_id: int):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    try:
        conversation = project.conversation
    except Conversation.DoesNotExist:
        return []

    messages = conversation.messages.order_by("created_at")
    return [
        MessageSchema(
            id=m.id,
            role=m.role,
            content=m.content,
            processing=m.processing,
            created_at=m.created_at,
        )
        for m in messages
    ]


@api.get("/messages/{message_id}/", response=MessageSchema)
def get_message(request, message_id: int):
    try:
        msg = Message.objects.get(id=message_id)
    except Message.DoesNotExist:
        raise HttpError(404, "Message not found")

    return MessageSchema(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        processing=msg.processing,
        created_at=msg.created_at,
    )


@api.post("/projects/{project_id}/approve/", response=ApproveResponseSchema)
def approve_project(request, project_id: int):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    if not hasattr(project, "tech_spec"):
        raise HttpError(
            400, "No TechSpec found. Chat with the Tech Lead first."
        )

    project.status = Project.STATUS_APPROVED
    project.save(update_fields=["status"])

    from .tasks import generate_dev_tasks

    generate_dev_tasks.delay(project_id)

    return ApproveResponseSchema(
        status="approved", message="Dev tasks generation started."
    )


@api.post("/projects/{project_id}/start/", response=StartProjectResponseSchema)
def start_project(request, project_id: int):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    if project.status not in [
        Project.STATUS_APPROVED,
        Project.STATUS_IN_PROGRESS,
    ]:
        raise HttpError(
            400, "Project must be approved before it can be started."
        )

    github_error = None
    if not project.github_repo_url:
        from .github import create_github_repo

        try:
            project.github_repo_url = create_github_repo(
                project.name, project.description
            )
            project.status = Project.STATUS_IN_PROGRESS
            project.save(update_fields=["status", "github_repo_url"])
        except Exception as exc:
            github_error = str(exc)

    return StartProjectResponseSchema(
        status=project.status,
        github_repo_url=project.github_repo_url,
        github_error=github_error,
    )


TERMINAL_STATUSES = {Project.STATUS_COMPLETED, Project.STATUS_ABORTED}


@api.post("/projects/{project_id}/mark-status/", response=ProjectStatusResponseSchema)
def mark_project_status(request, project_id: int, status: str):
    if status not in (Project.STATUS_COMPLETED, Project.STATUS_ABORTED):
        raise HttpError(400, "status must be 'completed' or 'aborted'")
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")
    if project.status in TERMINAL_STATUSES:
        raise HttpError(400, f"Project is already {project.status}.")
    project.status = status
    project.save(update_fields=["status"])
    return ProjectStatusResponseSchema(status=project.status)


@api.post("/dev-agent/run/", response=RunDevAgentsResponseSchema)
def run_dev_agents(request):
    from .models import DevTask, Project, Workspace

    available_count = Workspace.objects.filter(current_task=None).count()
    tasks = (
        DevTask.objects.filter(
            status=DevTask.STATUS_PENDING,
            project__status=Project.STATUS_IN_PROGRESS,
        )
        .exclude(
            blocked_by__status__in=[DevTask.STATUS_PENDING, DevTask.STATUS_IN_PROGRESS]
        )
        .order_by("project", "order", "priority")
    )
    total = tasks.count()
    tasks_to_queue = tasks[:available_count]

    from .tasks import run_dev_task

    for task in tasks_to_queue:
        run_dev_task.delay(task.id)

    queued = len(tasks_to_queue)
    skipped = total - queued
    return RunDevAgentsResponseSchema(
        queued=queued,
        skipped=skipped,
        message=f"Queued {queued} task(s). {skipped} skipped (no free workspace)."
        if skipped
        else f"Queued {queued} task(s).",
    )


@api.get("/projects/{project_id}/tasks/", response=list[DevTaskSchema])
def get_tasks(request, project_id: int):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    tasks = DevTask.objects.filter(project=project).prefetch_related(
        "blocked_by"
    )
    return [
        DevTaskSchema(
            id=t.id,
            title=t.title,
            description=t.description,
            status=t.status,
            priority=t.priority,
            order=t.order,
            blocked_by=[b.id for b in t.blocked_by.all()],
        )
        for t in tasks
    ]
