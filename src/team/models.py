from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Project(BaseModel):
    STATUS_DRAFT = "draft"
    STATUS_PLANNING = "planning"
    STATUS_APPROVED = "approved"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_ABORTED = "aborted"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PLANNING, "Planning"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_ABORTED, "Aborted"),
        (STATUS_COMPLETED, "Completed"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )

    def __str__(self):
        return self.name


class Conversation(BaseModel):
    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name="conversation"
    )

    def __str__(self):
        return f"Tech Lead Conversation for {self.project}"


class Message(BaseModel):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    processing = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class TechSpec(models.Model):
    project = models.OneToOneField(
        Project, on_delete=models.CASCADE, related_name="tech_spec"
    )
    content = models.TextField()
    version = models.IntegerField(default=1)

    def __str__(self):
        return f"TechSpec v{self.version} for {self.project}"


class DevTask(models.Model):
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_DONE = "done"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_DONE, "Done"),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="dev_tasks"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    priority = models.IntegerField(default=0)
    order = models.IntegerField(default=0)
    blocked_by = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="blocks"
    )

    class Meta:
        ordering = ["order", "priority"]

    def __str__(self):
        return self.title
