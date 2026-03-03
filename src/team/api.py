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
        raise HttpError(400, "No TechSpec found. Chat with the Tech Lead first.")

    project.status = Project.STATUS_APPROVED
    project.save(update_fields=["status"])

    from .tasks import generate_dev_tasks
    generate_dev_tasks.delay(project_id)

    return ApproveResponseSchema(status="approved", message="Dev tasks generation started.")


@api.get("/projects/{project_id}/tasks/", response=list[DevTaskSchema])
def get_tasks(request, project_id: int):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        raise HttpError(404, "Project not found")

    tasks = DevTask.objects.filter(project=project).prefetch_related("blocked_by")
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
