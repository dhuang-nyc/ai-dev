from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse

from .models import Conversation, DevTask, Message, Project, TechSpec


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "status", "created_at", "updated_at"]
    list_filter = ["status"]
    search_fields = ["name", "description"]
    change_list_template = "team/project_changelist.html"

    def change_view(self, request, object_id, form_url="", extra_context=None):
        return HttpResponseRedirect(
            reverse("admin:team_project_chat", args=[object_id])
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:project_id>/chat/",
                self.admin_site.admin_view(self.chat_view),
                name="team_project_chat",
            ),
        ]
        return custom_urls + urls

    def chat_view(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)

        conversation = None
        messages = []
        try:
            conversation = project.conversation
            messages = list(conversation.messages.order_by("created_at"))
        except Conversation.DoesNotExist:
            pass

        tech_spec = None
        try:
            tech_spec = project.tech_spec
        except TechSpec.DoesNotExist:
            pass

        dev_tasks = []
        if project.status in [Project.STATUS_APPROVED, Project.STATUS_IN_PROGRESS]:
            dev_tasks = list(
                project.dev_tasks.prefetch_related("blocked_by").order_by("order", "priority")
            )

        context = {
            **self.admin_site.each_context(request),
            "title": f"Tech Lead Chat — {project.name}",
            "project": project,
            "messages": messages,
            "tech_spec": tech_spec,
            "dev_tasks": dev_tasks,
            "opts": self.model._meta,
        }
        return render(request, "team/project_chat.html", context)


@admin.register(DevTask)
class DevTaskAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "status", "priority", "order"]
    list_filter = ["status", "project"]
    search_fields = ["title", "description"]
    filter_horizontal = ["blocked_by"]
