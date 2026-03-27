import json
import logging
import time
from decimal import Decimal

from anthropic import Anthropic

from .utils.helpers import compute_cost

logger = logging.getLogger(__name__)

PM_MODEL = "claude-sonnet-4-6"
CLIENT = Anthropic()
MAX_TOKENS = 8000


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a seasoned Product Manager with a track record of shipping products people actually use. You are sharp, direct, and allergic to vague feature requests.

Your job is to take a raw idea and turn it into a clear, actionable brief that a Tech Lead can use to start building immediately — no back-and-forth needed.

## Your Conversation Flow

Work through these four stages **in order**. Ask **one focused question at a time** — don't dump multiple questions at once.

### Stage 1 — Problem Discovery
Don't start with features. Start with pain.
- Who has this problem? Be specific (not "everyone", but "solo founders who...").
- What are they doing today to solve it? What's broken about that?
- How painful is this, really? (Nice-to-have vs. I'll-pay-for-this-today)
- Push back on vague answers. "Build an app to manage tasks" → "Who's managing what tasks and why does their current tool fail them?"

### Stage 2 — Solution Design
Only after the problem is sharp, explore solutions.
- What's the minimum viable thing that solves the core pain?
- What are the 3-5 features that define this product's core value? (Not the roadmap — the MVP.)
- What explicitly is OUT of scope for v1? Force trade-offs.
- Are there technical constraints or existing systems to integrate with?

### Stage 3 — PMF Assessment
Quick, honest gut-check — not a market research project.
- Who is the beachhead user? (The first 10 customers, not the TAM.)
- What are 2-3 direct/indirect competitors and why does this beat them for that specific user?
- What's the distribution strategy? Where do these users hang out?
- One-sentence differentiation: "The only [product] that [does X] for [user Y]."

### Stage 4 — Brief & Handoff
When you have enough signal (typically 6-10 exchanges):
1. Call `finalize_brief` to crystallise the scope.
2. Present a clean summary to the user and ask: "Ready to hand this off to the Tech Lead and start planning?"
3. Only call `start_project` after the user explicitly confirms they want to proceed.

## Tone & Style
- Be direct. Skip pleasantries after the opening.
- When the user gives a vague answer, name it and redirect: "That's a roadmap, not an MVP. What's the one thing that makes this worth building?"
- When you spot a PMF risk, say it clearly: "This is a crowded space. What makes a [user] choose this over [competitor]?"
- Celebrate sharp answers briefly and move on.
- Never ask more than one question per message.
"""


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "finalize_brief",
        "description": (
            "Call this when you have enough information to crystallise the product brief. "
            "Captures the full scope so you can present a clean summary to the user. "
            "After calling this, present the brief to the user and ask if they're ready to hand off to the Tech Lead. "
            "Only call `start_project` after the user explicitly confirms."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": (
                        "A concise, memorable project name (2-5 words, title case). "
                        "e.g. 'CodeReview Inbox', 'Solo CRM', 'Fleet Pulse'."
                    ),
                },
                "problem_statement": {
                    "type": "string",
                    "description": "1-2 sentences: who has the problem, what they do today, and why that fails.",
                },
                "target_user": {
                    "type": "string",
                    "description": "Specific description of the beachhead user segment.",
                },
                "proposed_solution": {
                    "type": "string",
                    "description": "2-3 sentences on what the product does and its core value proposition.",
                },
                "core_features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-6 MVP features as short action phrases.",
                },
                "non_goals": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Explicit v1 exclusions.",
                },
                "pmf_rationale": {
                    "type": "string",
                    "description": "1-2 sentences: beachhead market, key differentiator vs. alternatives.",
                },
                "tech_constraints": {
                    "type": "string",
                    "description": "Technical constraints or integrations. Empty string if none.",
                },
                "start_prompt": {
                    "type": "string",
                    "description": (
                        "The complete, self-contained prompt to feed directly to the Tech Lead. "
                        "Must include: Problem / Target User / Solution / MVP Features / "
                        "Out of Scope / PMF Context / Technical Constraints."
                    ),
                },
            },
            "required": [
                "project_name",
                "problem_statement",
                "target_user",
                "proposed_solution",
                "core_features",
                "non_goals",
                "pmf_rationale",
                "tech_constraints",
                "start_prompt",
            ],
            "additionalProperties": False,
        },
    },
    {
        "name": "start_project",
        "description": (
            "Call this ONLY after the user has explicitly confirmed they want to proceed. "
            "Creates a new project and kicks off the Tech Lead planning conversation. "
            "Use the project_name, project_description, and start_prompt from the finalize_brief you already produced."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "The project name from the finalize_brief.",
                },
                "project_description": {
                    "type": "string",
                    "description": (
                        "1-2 sentence description combining the problem + proposed solution. "
                        "This appears on the project card."
                    ),
                },
                "start_prompt": {
                    "type": "string",
                    "description": "The full structured prompt from finalize_brief to seed the Tech Lead conversation.",
                },
            },
            "required": ["project_name", "project_description", "start_prompt"],
            "additionalProperties": False,
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------


def _execute_pm_tool(
    name: str, tool_input: dict, pm_conversation_id: int
) -> tuple[str, dict | None]:
    """
    Execute a PM tool. Returns (json_result_string, project_created_dict | None).
    project_created_dict is set when start_project fires successfully.
    """
    if name == "finalize_brief":
        # No DB writes — just acknowledge so the model can present the brief to the user.
        return json.dumps({"success": True}), None

    if name == "start_project":
        from team.models import (
            Conversation,
            Message,
            PMConversation,
            Project,
        )
        from team.tasks import process_chat_message

        pm_conv = PMConversation.objects.get(id=pm_conversation_id)
        if pm_conv.project_id:
            return (
                json.dumps(
                    {
                        "error": "A project already exists for this conversation.",
                        "project_id": pm_conv.project_id,
                    }
                ),
                None,
            )

        project = Project.objects.create(
            name=tool_input["project_name"],
            description=tool_input["project_description"],
            status=Project.STATUS_PLANNING,
        )

        # Link PM conversation to the newly created project
        PMConversation.objects.filter(id=pm_conversation_id).update(
            project=project
        )

        # Boot the Tech Lead conversation with the PM's start_prompt as the first user message
        conversation = Conversation.objects.create(project=project)
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_USER,
            content=tool_input["start_prompt"],
        )
        assistant_msg = Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content="",
            processing=True,
        )

        process_chat_message.delay(project.id, assistant_msg.id)

        logger.info(
            "PM started project %d (%s) from PM conversation %d",
            project.id,
            project.name,
            pm_conversation_id,
        )

        project_created = {
            "project_id": project.id,
            "assistant_message_id": assistant_msg.id,
        }
        return json.dumps({"success": True, **project_created}), project_created

    return json.dumps({"error": f"Unknown tool: {name}"}), None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_pm_with_history(
    pm_conversation_id: int,
    history: list[dict],
    new_user_message: str,
) -> dict:
    """
    Run one PM conversation turn.

    Returns:
        {
            "response": str,
            "brief": dict | None,
            "project_created": dict | None,
            "token_cost": Decimal,
            "response_time_ms": int,
        }
    """
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": new_user_message})

    brief_result = None
    project_created = None
    response = None
    total_input_tokens = 0
    total_output_tokens = 0
    start = time.monotonic()

    while True:
        response = CLIENT.messages.create(
            model=PM_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            logger.info("PM calling tool: %s %s", block.name, block.input)
            result_str, meta = _execute_pm_tool(
                block.name, block.input, pm_conversation_id
            )

            if block.name == "finalize_brief":
                brief_result = block.input
            elif block.name == "start_project" and meta:
                project_created = meta

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                }
            )

        messages.append({"role": "user", "content": tool_results})

    elapsed_ms = int((time.monotonic() - start) * 1000)
    cost = compute_cost(PM_MODEL, total_input_tokens, total_output_tokens)

    logger.info(
        "PM turn: %d input + %d output tokens, cost=$%s, %dms",
        total_input_tokens,
        total_output_tokens,
        cost,
        elapsed_ms,
    )

    text_blocks = [b.text for b in response.content if b.type == "text"]
    return {
        "response": "\n".join(text_blocks),
        "brief": brief_result,
        "project_created": project_created,
        "token_cost": cost,
        "response_time_ms": elapsed_ms,
    }
