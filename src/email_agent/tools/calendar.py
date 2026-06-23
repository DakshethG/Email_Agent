"""Google Calendar write tool — used only by the confirmed create-event path.

Per CLAUDE.md §4.4, this tool is never exposed to the model (it is not in
`tools/registry.py`'s allow-list and never appears in the LLM's `tools` list).
`core/agent.py::Agent.create_event` calls it directly, only after a human has
confirmed a `create_event` PendingAction.

Slug and schema verified live via `composio.tools.get(tools=["GOOGLECALENDAR_CREATE_EVENT"])`
in Phase 2; re-verify if Composio's schema changes.
"""

from __future__ import annotations

from typing import Any

CREATE_EVENT_TOOL_SLUG = "GOOGLECALENDAR_CREATE_EVENT"


def build_create_event_arguments(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a confirmed `create_event` PendingAction payload to
    GOOGLECALENDAR_CREATE_EVENT arguments.

    `payload` is expected to have the shape produced by the agent's
    `propose_calendar_event` tool: title, start, end, timezone, location,
    attendees, description, ambiguous_fields.
    """
    arguments: dict[str, Any] = {
        "start_datetime": payload["start"],
        "timezone": payload["timezone"],
    }
    if payload.get("end"):
        arguments["end_datetime"] = payload["end"]
    if payload.get("title"):
        arguments["summary"] = payload["title"]
    if payload.get("location"):
        arguments["location"] = payload["location"]
    if payload.get("description"):
        arguments["description"] = payload["description"]
    if payload.get("attendees"):
        arguments["attendees"] = payload["attendees"]
    return arguments
