from datetime import datetime
from typing import Optional

from ninja import Schema


class ChatRequestSchema(Schema):
    content: str


class ChatResponseSchema(Schema):
    user_message_id: int
    assistant_message_id: int


class MessageSchema(Schema):
    id: int
    role: str
    content: str
    processing: bool
    created_at: datetime


class DevTaskSchema(Schema):
    id: int
    title: str
    description: str
    status: str
    priority: int
    order: int
    blocked_by: list[int]


class ApproveResponseSchema(Schema):
    status: str
    message: str


class StartProjectResponseSchema(Schema):
    status: str
    github_repo_url: Optional[str]
    github_error: Optional[str]


class CreateFromIdeaRequestSchema(Schema):
    idea: str


class CreateFromIdeaResponseSchema(Schema):
    project_id: int
    assistant_message_id: int


class RunDevAgentsResponseSchema(Schema):
    queued: int
    skipped: int
    message: str


class ProjectStatusResponseSchema(Schema):
    status: str


class ProjectDeleteResponseSchema(Schema):
    deleted: bool
