"""Gmail tool allow-list and send-path helpers.

Per CLAUDE.md §4.4, only read-only and inherently-safe tools are in the
registry (ALLOWED_TOOL_SLUGS). SEND_EMAIL_SLUG is deliberately excluded —
the model never sees it; only Agent.send_email() calls it after explicit
human approval (Phase 4).

Slugs verified against the live Composio GMAIL toolkit; re-verify via
scripts/discover_send_tool.py if Composio changes them.
"""

from __future__ import annotations

from typing import Any

READ_ONLY_GMAIL_TOOLS: list[str] = [
    "GMAIL_FETCH_EMAILS",  # list/search messages
    "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",  # get a single message
    "GMAIL_FETCH_MESSAGE_BY_THREAD_ID",  # get all messages in a thread
]

# Phase 3: a draft is never sent, so creating one is inherently safe and is
# allowed directly here -- unlike calendar-event creation (Phase 2), which
# has a real-world side effect and goes through the local-tool/confirm
# pattern instead.
DRAFT_GMAIL_TOOLS: list[str] = [
    "GMAIL_CREATE_EMAIL_DRAFT",  # saves a draft linked to a thread; never sends
]

# Phase 4: send slug — NOT in ALLOWED_TOOL_SLUGS. The model never calls this.
# Only Agent.send_email() calls it, after explicit owner approval (CLAUDE.md §4.1).
# Verify the exact slug via scripts/discover_send_tool.py before first use.
SEND_EMAIL_SLUG = "GMAIL_SEND_EMAIL"


def build_send_email_arguments(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a send_email PendingAction payload to Composio GMAIL_SEND_EMAIL args.

    Verify against the live schema (scripts/discover_send_tool.py) if the
    Composio parameter names change.
    """
    args: dict[str, Any] = {
        "recipient_email": payload["recipient_email"],
        "body": payload["body"],
    }
    if payload.get("thread_id"):
        args["thread_id"] = payload["thread_id"]
    return args
