"""Block Kit message builders for email and calendar proposals.

Shared between slack_app.py (interactive Bolt messages) and
triggers/gmail_watch.py (proactive trigger posts). No Bolt dependency —
pure data builders that return list[dict] block structures.
"""

from __future__ import annotations

from email_agent.interfaces.approval_handlers import (
    ALREADY_PROCESSED,
    AMBIGUOUS,
    ERROR,
    IGNORED,
    SENT,
)


def send_email_blocks(action_id: str, payload: dict) -> list[dict]:
    """Block Kit layout for a proposed-reply approval message."""
    body = payload.get("body", "")
    preview = body[:300] + ("…" if len(body) > 300 else "")
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Proposed reply* to `{payload.get('recipient_email', '?')}`:\n"
                    f"```{preview}```"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Send"},
                    "action_id": "approve_send",
                    "value": action_id,
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✏️ Edit"},
                    "action_id": "edit_send",
                    "value": action_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✖️ Ignore"},
                    "action_id": "ignore_send",
                    "value": action_id,
                    "style": "danger",
                },
            ],
        },
    ]


def create_event_blocks(action_id: str, payload: dict) -> list[dict]:
    """Block Kit layout for a proposed calendar event.

    If `ambiguous_fields` is non-empty the Confirm button is omitted — the
    event cannot be created until the human clarifies and re-asks.
    """
    ambiguous = payload.get("ambiguous_fields") or []

    header = "*Proposed calendar event*"
    if ambiguous:
        header += " — ⚠️ Needs clarification"

    lines = [header]
    lines.append(f"*Title:* {payload.get('title') or '_(none)_'}")

    start = payload.get("start") or "_(unknown)_"
    end = payload.get("end") or "_(unknown)_"
    tz = payload.get("timezone") or ""
    lines.append(f"*When:* {start} → {end}  {tz}".rstrip())

    if payload.get("location"):
        lines.append(f"*Location:* {payload['location']}")
    if payload.get("attendees"):
        lines.append(f"*Attendees:* {', '.join(payload['attendees'])}")
    if payload.get("description"):
        lines.append(f"*Notes:* {payload['description']}")
    if ambiguous:
        lines.append(f"\n⚠️ Unclear: {', '.join(ambiguous)}. Please clarify and ask again.")

    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}
    ]

    elements: list[dict] = []
    if not ambiguous:
        elements.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Create Event"},
                "action_id": "confirm_event",
                "value": action_id,
                "style": "primary",
            }
        )
    elements.append(
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "✖️ Dismiss"},
            "action_id": "dismiss_event",
            "value": action_id,
        }
    )
    blocks.append({"type": "actions", "elements": elements})
    return blocks


EMAIL_TERMINAL = {
    SENT: "✅ Sent.",
    IGNORED: "✖️ Ignored.",
    ALREADY_PROCESSED: "⚠️ This proposal was already processed.",
    ERROR: "❌ Send failed — check logs.",
}

CALENDAR_TERMINAL = {
    SENT: "✅ Event created.",
    IGNORED: "✖️ Dismissed.",
    ALREADY_PROCESSED: "⚠️ This proposal was already processed.",
    AMBIGUOUS: "⚠️ Can't create — event details are ambiguous. Please clarify.",
    ERROR: "❌ Event creation failed — check logs.",
}
