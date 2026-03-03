import json

from agno.agent import Agent
from agno.models.anthropic import Claude
from anthropic import Anthropic

SYSTEM_PROMPT = """You are a senior Tech Lead helping to plan a software feature.

Your role is to:
1. Understand the feature requirements by asking ONE clarifying question at a time
2. Iterate on the requirements based on the user's answers
3. When you have enough information, produce a comprehensive TechSpec

When producing a TechSpec, use this EXACT markdown structure:
## Overview
[Brief description of the feature]

## Goals & Non-Goals
[What this feature will and won't do]

## Architecture
[High-level architecture decisions]

## Data Models
[Database models and their fields]

## API Endpoints
[API endpoints with methods and descriptions]

## Key Workflows
[Step-by-step description of key user flows]

## Implementation Plan
[Ordered list of implementation steps]

## Open Questions
[Any remaining uncertainties]

After the TechSpec, include a task breakdown:
## Tasks
[Numbered list of dev tasks with titles and descriptions]

Guidelines:
- Ask one focused question at a time to avoid overwhelming the user
- Be concrete and specific in your technical recommendations
- Consider scalability, maintainability, and security
- Flag potential risks and trade-offs
- Only produce the TechSpec when you feel you have sufficient information"""

TASK_EXTRACTION_PROMPT = """You are given a TechSpec document. Extract the development tasks from it.

Return ONLY a JSON array with no other text, no markdown code blocks, just raw JSON.

Each task object must have:
- "title": string (short task title)
- "description": string (detailed description)
- "priority": integer (1=highest, 5=lowest)
- "blocked_by": array of strings (titles of tasks this task depends on, empty array if none)

Example:
[
  {{"title": "Set up database models", "description": "Create the core data models", "priority": 1, "blocked_by": []}},
  {{"title": "Build API endpoints", "description": "Implement REST API", "priority": 2, "blocked_by": ["Set up database models"]}}
]

TechSpec:
{spec_content}"""

PROJECT_EXTRACTION_PROMPT = """
You are given an idea for a software project. Extract the project name and formatted description from it.

Respond with ONLY a raw JSON object — no markdown, no code blocks.

Example:
{"name": "Project Name", "description": "Project Description"}

Idea: {idea}
"""


TECH_LEAD_MODEL = "claude-sonnet-4-6"


def build_tech_lead_agent() -> Agent:
    return Agent(
        name="Team Lead",
        model=Claude(id=TECH_LEAD_MODEL),
        instructions=SYSTEM_PROMPT,
        markdown=True,
    )


def run_tech_lead_with_history(
    history: list[dict], new_user_message: str
) -> str:
    client = Anthropic()

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": new_user_message})

    response = client.messages.create(
        model=TECH_LEAD_MODEL,
        max_tokens=8096,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return response.content[0].text


def extract_project_info(idea: str) -> dict:
    agent = build_tech_lead_agent()
    response = agent.run(PROJECT_EXTRACTION_PROMPT.format(idea=idea))
    return json.loads(response.content.strip())


def extract_tasks(tech_spec: str) -> list[dict]:
    agent = build_tech_lead_agent()
    response = agent.run(TASK_EXTRACTION_PROMPT.format(spec_content=tech_spec))
    return json.loads(response.content.strip())
