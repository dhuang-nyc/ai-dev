from datetime import datetime
from decimal import Decimal
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
    token_cost: Optional[Decimal] = None
    response_time_ms: Optional[int] = None


class DevTaskSchema(Schema):
    id: int
    title: str
    description: str
    status: str
    priority: int
    order: int
    blocked_by: list[int]
    pr_url: Optional[str]
    branch_name: str
    agent_log: str
    claude_prompt: str
    total_cost: Optional[Decimal] = None
    total_duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class UpdateTaskSchema(Schema):
    title: Optional[str] = None
    description: Optional[str] = None
    claude_prompt: Optional[str] = None
    status: Optional[str] = None


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


class DashboardTaskSchema(Schema):
    id: int
    title: str
    status: str
    priority: int
    project_id: int
    project_name: str
    pr_url: Optional[str]
    blocked_by: list[int]
    has_logs: bool
    total_cost: Optional[Decimal] = None
    total_duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class WorkspaceSchema(Schema):
    id: int
    name: str
    is_available: bool
    current_task_id: Optional[int]
    current_task_title: Optional[str]


class TechSpecSchema(Schema):
    content: str
    version: int


class ProjectListSchema(Schema):
    id: int
    name: str
    description: str
    status: str
    github_repo_url: Optional[str]
    created_at: datetime
    has_tech_spec: bool
    task_count: int
    total_cost: Optional[Decimal] = None
    total_agent_time_ms: Optional[int] = None


class ProjectDetailSchema(Schema):
    id: int
    name: str
    description: str
    status: str
    github_repo_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    tech_spec: Optional[TechSpecSchema]
    total_cost: Optional[Decimal] = None
    total_agent_time_ms: Optional[int] = None
    has_pm_chat: bool
    has_tasks: bool


class PMMessageSchema(Schema):
    id: int
    role: str
    content: str
    processing: bool
    created_at: datetime
    token_cost: Optional[Decimal] = None
    response_time_ms: Optional[int] = None
    conversation_project_id: Optional[int] = None


class PMConversationSchema(Schema):
    id: int
    project_id: Optional[int]
    created_at: datetime


class PMConversationListItemSchema(Schema):
    id: int
    project_id: Optional[int]
    project_name: Optional[str]
    message_count: int
    created_at: datetime
    preview: Optional[str]  # first user message, truncated


class PMChatResponseSchema(Schema):
    user_message_id: int
    assistant_message_id: int
