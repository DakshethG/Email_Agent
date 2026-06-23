"""Builds the OpenAI-format tool schemas exposed to the model.

Schemas are fetched live from Composio (CLAUDE.md §6 — do not hardcode tool
schemas from memory) and filtered to the curated per-toolkit allow-lists
(currently just tools/gmail.py).
"""

from __future__ import annotations

from typing import Any

from composio import Composio

from email_agent.safety.guards import validate_no_destructive_tools
from email_agent.tools.gmail import DRAFT_GMAIL_TOOLS, READ_ONLY_GMAIL_TOOLS

ALLOWED_TOOL_SLUGS: list[str] = [*READ_ONLY_GMAIL_TOOLS, *DRAFT_GMAIL_TOOLS]

# Validate at import time: catches accidental additions to ALLOWED_TOOL_SLUGS.
validate_no_destructive_tools(ALLOWED_TOOL_SLUGS)


def build_tool_schemas(composio: Composio, user_id: str) -> list[dict[str, Any]]:
    """Fetch OpenAI-format tool schemas for the allow-listed tool slugs.

    Composio includes a `function.strict` key (often `null`) that NIM's
    chat-completions endpoint rejects with "Extra inputs are not permitted",
    so it is stripped here.
    """
    tools = composio.tools.get(user_id=user_id, tools=list(ALLOWED_TOOL_SLUGS))
    for tool in tools:
        tool.get("function", {}).pop("strict", None)
    return tools
