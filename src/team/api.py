import logging

from ninja import NinjaAPI
from ninja.errors import HttpError

logger = logging.getLogger(__name__)

from .models import Conversation, DevTask, Message, Project
from .schemas import (
    ApproveResponseSchema,
    ChatRequestSchema,
    ChatResponseSchema,
    CreateFromIdeaRequestSchema,
    CreateFromIdeaResponseSchema,
    DashboardTaskSchema,
    DevTaskSchema,
    MessageSchema,
    ProjectDetailSchema,
    ProjectListSchema,
    ProjectStatusResponseSchema,
    RunDevAgentsResponseSchema,
    StartProjectResponseSchema,
    TechSpecSchema,
    UpdateTaskSchema,
    WorkspaceSchema,
)

api = NinjaAPI()


@api.get("/tasks/", response=list[DashboardTaskSchema])
def list_active_tasks(request):
    tasks = (
        DevTask.objects.filter(
            status__in=[
                DevTask.STATUS_PENDING,
                DevTask.STATUS_IN_PROGRESS,
                DevTask.STATUS_PR_OPEN,
            ],
            project__status=Project.STATUS_IN_PROGRESS,
        )
        .select_related("project")
        .order_by("status", "project", "order", "priority")
    )
    return [
        DashboardTaskSchema(
            id=t.id,
            title=t.title,
            status=t.status,
            priority=t.priority,
            project_id=t.project_id,
            project_name=t.project.name,
            pr_url=t.pr_url,
            has_logs=bool(t.agent_log and t.agent_log.strip()),
        )
        for t in tasks
    ]


@api.get("/workspaces/", response=list[WorkspaceSchema])
def list_workspaces(request):
    from .models import Workspace

    workspaces = Workspace.objects.select_related("current_task").order_by(
        "name"
    )
    return [
        WorkspaceSchema(
            id=w.id,
            name=w.name,
            is_available=w.is_available,
            current_task_id=w.current_task_id,
            current_task_title=w.current_task.title if w.current_task else None,
        )
        for w in workspaces
    ]


@api.get("/projects/", response=list[ProjectListSchema])
def list_projects(request):
    from django.db.models import Count, Exists, OuterRef
    from .models import TechSpec

    projects = Project.objects.annotate(
        task_count=Count("dev_tasks"),
        has_tech_spec=Exists(TechSpec.objects.filter(project=OuterRef("pk"))),
    ).order_by("-created_at")
    return list(projects)


@api.get("/projects/{project_id}/", response=ProjectDetailSchema)
def get_project(request, project_id: int):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    tech_spec = None
    try:
        spec = project.tech_spec
        tech_spec = TechSpecSchema(content=spec.content, version=spec.version)
    except Exception:
        pass

    return ProjectDetailSchema(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        github_repo_url=project.github_repo_url,
        created_at=project.created_at,
        updated_at=project.updated_at,
        tech_spec=tech_spec,
    )


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
        from .github import upsert_github_repo

        try:
            tech_spec_content = ""
            try:
                tech_spec_content = project.tech_spec.content
            except Exception:
                pass
            project.github_repo_url = upsert_github_repo(
                project.name,
                project.description,
                readme_content=tech_spec_content,
            )
            project.status = Project.STATUS_IN_PROGRESS
            project.save(update_fields=["status", "github_repo_url"])
        except Exception as exc:
            github_error = str(exc)

    if not github_error and project.status == Project.STATUS_IN_PROGRESS:
        from .tasks import project_manager_assign

        project_manager_assign.delay()

    return StartProjectResponseSchema(
        status=project.status,
        github_repo_url=project.github_repo_url,
        github_error=github_error,
    )


TERMINAL_STATUSES = {Project.STATUS_COMPLETED, Project.STATUS_ABORTED}


@api.post(
    "/projects/{project_id}/mark-status/", response=ProjectStatusResponseSchema
)
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
            blocked_by__status__in=[
                s for s, _ in DevTask.STATUS_CHOICES
                if s not in (DevTask.STATUS_DONE, DevTask.STATUS_ABORTED)
            ]
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
        message=(
            f"Queued {queued} task(s). {skipped} skipped (no free workspace)."
            if skipped
            else f"Queued {queued} task(s)."
        ),
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
            pr_url=t.pr_url,
            branch_name=t.branch_name,
            agent_log=t.agent_log,
            claude_prompt=t.claude_prompt,
        )
        for t in tasks
    ]


@api.get("/tasks/{task_id}/", response=DevTaskSchema)
def get_task(request, task_id: int):
    try:
        t = DevTask.objects.prefetch_related("blocked_by").get(id=task_id)
    except DevTask.DoesNotExist:
        raise HttpError(404, "Task not found")
    return DevTaskSchema(
        id=t.id,
        title=t.title,
        description=t.description,
        status=t.status,
        priority=t.priority,
        order=t.order,
        blocked_by=[b.id for b in t.blocked_by.all()],
        pr_url=t.pr_url,
        branch_name=t.branch_name,
        agent_log=t.agent_log,
        claude_prompt=t.claude_prompt,
    )


@api.patch("/tasks/{task_id}/", response=DevTaskSchema)
def update_task(request, task_id: int, payload: UpdateTaskSchema):
    try:
        t = DevTask.objects.prefetch_related("blocked_by").get(id=task_id)
    except DevTask.DoesNotExist:
        raise HttpError(404, "Task not found")
    if t.status != DevTask.STATUS_PENDING:
        raise HttpError(400, f"Cannot edit task with status '{t.status}'.")
    update_fields = []
    for field in ("title", "description", "claude_prompt"):
        val = getattr(payload, field)
        if val is not None:
            setattr(t, field, val)
            update_fields.append(field)
    if update_fields:
        t.save(update_fields=update_fields)
    return DevTaskSchema(
        id=t.id,
        title=t.title,
        description=t.description,
        status=t.status,
        priority=t.priority,
        order=t.order,
        blocked_by=[b.id for b in t.blocked_by.all()],
        pr_url=t.pr_url,
        branch_name=t.branch_name,
        agent_log=t.agent_log,
        claude_prompt=t.claude_prompt,
    )


@api.post("/github/webhook/")
def github_webhook(request):
    import json as _json
    from django.http import HttpResponse
    from .github import verify_webhook_signature

    event = request.headers.get("X-GitHub-Event", "")
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_webhook_signature(request.body, signature):
        return HttpResponse("Invalid signature", status=401)

    if event != "pull_request":
        return {"ok": True}

    payload = _json.loads(request.body)
    action = payload.get("action")
    pr = payload.get("pull_request", {})

    if action != "closed" or not pr.get("merged"):
        return {"ok": True}

    pr_url = pr.get("html_url", "")
    try:
        task = DevTask.objects.get(pr_url=pr_url)
    except DevTask.DoesNotExist:
        logger.warning("Webhook: no task found for PR %s", pr_url)
        return {"ok": True}

    task.status = DevTask.STATUS_DONE
    task.save(update_fields=["status"])
    logger.info("Task %s marked done via webhook (PR %s)", task.id, pr_url)

    from .tasks import project_manager_assign
    project_manager_assign.delay()

    return {"ok": True}
