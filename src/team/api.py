import logging

from django.contrib.auth import authenticate
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from ninja.security import django_auth

logger = logging.getLogger(__name__)

from .models import (
    Conversation,
    DevTask,
    Message,
    PMConversation,
    PMMessage,
    Project,
)
from .schemas import (
    ApproveResponseSchema,
    ChatRequestSchema,
    ChatResponseSchema,
    CreateFromIdeaRequestSchema,
    CreateFromIdeaResponseSchema,
    DashboardTaskSchema,
    DevTaskSchema,
    MessageSchema,
    PMChatResponseSchema,
    PMConversationListItemSchema,
    PMConversationSchema,
    PMMessageSchema,
    ProjectDetailSchema,
    ProjectListSchema,
    ProjectStatusResponseSchema,
    RunDevAgentsResponseSchema,
    StartProjectResponseSchema,
    TechSpecSchema,
    UpdateTaskSchema,
    WorkspaceSchema,
)

api = NinjaAPI(auth=django_auth)


class LoginSchema(Schema):
    username: str
    password: str


class AuthUserSchema(Schema):
    username: str | None
    authenticated: bool


@api.get("/auth/me/", auth=None, response=AuthUserSchema)
def auth_me(request):
    from django.middleware.csrf import get_token

    get_token(
        request
    )  # ensures CSRF cookie is set for subsequent POST requests
    if request.user.is_authenticated:
        return AuthUserSchema(
            username=request.user.username, authenticated=True
        )
    return AuthUserSchema(username=None, authenticated=False)


@api.post("/auth/login/", auth=None, response=AuthUserSchema)
def auth_login(request, payload: LoginSchema):
    user = authenticate(
        request, username=payload.username, password=payload.password
    )
    if user is None:
        raise HttpError(401, "Invalid credentials")
    django_login(request, user)
    return AuthUserSchema(username=user.username, authenticated=True)


@api.post("/auth/logout/", auth=None)
def auth_logout(request):
    django_logout(request)
    return {"ok": True}


@api.get("/tasks/", response=list[DashboardTaskSchema])
def list_active_tasks(request):
    STATUS_ORDER = {
        DevTask.STATUS_PR_OPEN: 0,
        DevTask.STATUS_IN_PROGRESS: 1,
        DevTask.STATUS_ERROR: 2,
        DevTask.STATUS_PENDING: 3,
        DevTask.STATUS_DONE: 4,
    }
    from django.db.models import Case, IntegerField, Value, When

    tasks = (
        DevTask.objects.filter(
            status__in=STATUS_ORDER.keys(),
            project__status=Project.STATUS_IN_PROGRESS,
        )
        .select_related("project")
        .annotate(
            status_order=Case(
                *[
                    When(status=s, then=Value(i))
                    for s, i in STATUS_ORDER.items()
                ],
                default=Value(99),
                output_field=IntegerField(),
            )
        )
        .order_by("status_order", "project", "order", "priority")
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
            blocked_by=[b.id for b in t.blocked_by.all()],
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
                s
                for s, _ in DevTask.STATUS_CHOICES
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
    update_fields = []
    editable = t.status == DevTask.STATUS_PENDING
    for field in ("title", "description", "claude_prompt"):
        val = getattr(payload, field)
        if val is not None:
            if not editable:
                raise HttpError(
                    400, f"Cannot edit task fields when status is '{t.status}'."
                )
            setattr(t, field, val)
            update_fields.append(field)
    if payload.status is not None and payload.status != t.status:
        valid = {s for s, _ in DevTask.STATUS_CHOICES}
        if payload.status not in valid:
            raise HttpError(400, f"Invalid status '{payload.status}'.")
        t.status = payload.status
        update_fields.append("status")
        if (
            payload.status == DevTask.STATUS_DONE
            or payload.status == DevTask.STATUS_ABORTED
        ):
            from .tasks import cleanup_workspace_branch

            cleanup_workspace_branch.delay(t.id)

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


# ---------------------------------------------------------------------------
# PM Conversation endpoints
# ---------------------------------------------------------------------------


@api.get("/pm/conversations/", response=list[PMConversationListItemSchema])
def list_pm_conversations(request):
    from django.db.models import Count

    convs = (
        PMConversation.objects.select_related("project")
        .annotate(msg_count=Count("messages"))
        .order_by("-created_at")
    )
    result = []
    for c in convs:
        first_msg = (
            c.messages.filter(role=PMMessage.ROLE_USER)
            .order_by("created_at")
            .first()
        )
        preview = None
        if first_msg:
            preview = first_msg.content[:120] + (
                "\u2026" if len(first_msg.content) > 120 else ""
            )
        result.append(
            PMConversationListItemSchema(
                id=c.id,
                project_id=c.project_id,
                project_name=c.project.name if c.project_id else None,
                message_count=c.msg_count,
                created_at=c.created_at,
                preview=preview,
            )
        )
    return result


@api.get("/pm/conversations/{conversation_id}/", response=PMConversationSchema)
def get_pm_conversation(request, conversation_id: int):
    try:
        conv = PMConversation.objects.get(id=conversation_id)
    except PMConversation.DoesNotExist:
        raise HttpError(404, "PM conversation not found")
    return PMConversationSchema(
        id=conv.id, project_id=conv.project_id, created_at=conv.created_at
    )


@api.post("/pm/conversations/", response=PMConversationSchema)
def create_pm_conversation(request):
    conversation = PMConversation.objects.create()
    return PMConversationSchema(
        id=conversation.id,
        project_id=conversation.project_id,
        created_at=conversation.created_at,
    )


@api.post(
    "/pm/conversations/{conversation_id}/chat/", response=PMChatResponseSchema
)
def pm_chat(request, conversation_id: int, payload: ChatRequestSchema):
    try:
        conversation = PMConversation.objects.get(id=conversation_id)
    except PMConversation.DoesNotExist:
        raise HttpError(404, "PM conversation not found")

    user_msg = PMMessage.objects.create(
        conversation=conversation,
        role=PMMessage.ROLE_USER,
        content=payload.content,
    )
    assistant_msg = PMMessage.objects.create(
        conversation=conversation,
        role=PMMessage.ROLE_ASSISTANT,
        content="",
        processing=True,
    )

    from .tasks import process_pm_message

    process_pm_message.delay(conversation_id, assistant_msg.id)

    return PMChatResponseSchema(
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
    )


@api.get(
    "/pm/conversations/{conversation_id}/messages/",
    response=list[PMMessageSchema],
)
def get_pm_messages(request, conversation_id: int):
    try:
        conversation = PMConversation.objects.get(id=conversation_id)
    except PMConversation.DoesNotExist:
        raise HttpError(404, "PM conversation not found")

    messages = conversation.messages.order_by("created_at")
    project_id = conversation.project_id
    return [
        PMMessageSchema(
            id=m.id,
            role=m.role,
            content=m.content,
            processing=m.processing,
            created_at=m.created_at,
            conversation_project_id=project_id,
        )
        for m in messages
    ]


@api.delete("/pm/conversations/{conversation_id}/", response=str)
def delete_pm_conversation(request, conversation_id: int):
    try:
        conversation = PMConversation.objects.get(id=conversation_id)
    except PMConversation.DoesNotExist:
        raise HttpError(404, "PM conversation not found")
    conversation.delete()
    return "PM conversation deleted"


@api.get("/pm/messages/{message_id}/", response=PMMessageSchema)
def get_pm_message(request, message_id: int):
    try:
        msg = PMMessage.objects.select_related("conversation").get(
            id=message_id
        )
    except PMMessage.DoesNotExist:
        raise HttpError(404, "PM message not found")

    return PMMessageSchema(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        processing=msg.processing,
        created_at=msg.created_at,
        conversation_project_id=msg.conversation.project_id,
    )


@api.get(
    "/projects/{project_id}/pm-conversation/", response=list[PMMessageSchema]
)
def get_project_pm_conversation(request, project_id: int):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    try:
        conversation = project.pm_conversation
    except PMConversation.DoesNotExist:
        return []

    project_id_val = conversation.project_id
    messages = conversation.messages.order_by("created_at")
    return [
        PMMessageSchema(
            id=m.id,
            role=m.role,
            content=m.content,
            processing=m.processing,
            created_at=m.created_at,
            conversation_project_id=project_id_val,
        )
        for m in messages
    ]


@api.post("/github/webhook/", auth=None)
def github_webhook(request):
    import json as _json
    from django.http import HttpResponse
    from .github import (
        is_dev_agent,
        parse_pr_comment_event,
        verify_webhook_signature,
    )

    event = request.headers.get("X-GitHub-Event", "")
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_webhook_signature(request.body, signature):
        return HttpResponse("Invalid signature", status=401)

    payload = _json.loads(request.body)

    if event == "pull_request":
        return _handle_pr_merged(payload)

    comment_info = parse_pr_comment_event(event, payload)
    if comment_info and not is_dev_agent(comment_info["commenter"]):
        return _handle_pr_feedback(comment_info)

    return {"ok": True}


def _handle_pr_merged(payload: dict):
    """Mark a DevTask done when its PR is merged."""
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

    from .tasks import cleanup_workspace_branch, project_manager_assign

    cleanup_workspace_branch.delay(task.id)
    project_manager_assign.delay()

    return {"ok": True}


def _handle_pr_feedback(comment_info: dict):
    """Enqueue answer_pr_question when a non-dev-agent comments on an open PR."""
    pr_url = comment_info["pr_url"]
    commenter = comment_info["commenter"]

    if not pr_url:
        return {"ok": True}

    try:
        task = DevTask.objects.get(pr_url=pr_url, status=DevTask.STATUS_PR_OPEN)
    except DevTask.DoesNotExist:
        logger.info(
            "Webhook: no open task for PR %s (commenter: @%s) — ignoring",
            pr_url,
            commenter,
        )
        return {"ok": True}

    from .tasks import answer_pr_question

    answer_pr_question.delay(
        task.id,
        comment_info["body"],
        commenter,
        comment_url=comment_info.get("comment_url", ""),
        event_type=comment_info.get("event_type", "comment"),
        comment_id=comment_info.get("comment_id"),
        repo_full_name=comment_info.get("repo_full_name", ""),
        pr_number=comment_info.get("pr_number"),
    )

    logger.info(
        "Enqueued answer_pr_question for task %s (@%s, %s)",
        task.id,
        commenter,
        comment_info.get("event_type"),
    )

    return {"ok": True}
