"""Business logic for approval flows (send-email and calendar-event).

Extracted from the Slack adapter so classes can be unit-tested without the
Bolt framework. Slack action handlers in slack_app.py delegate here.

Per CLAUDE.md §4.1: the approval gate sits in front of every write path.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any  # noqa: F401 — Any used in string annotation

from email_agent.safety.guards import is_owner

if TYPE_CHECKING:
    from email_agent.core.agent import Agent
    from email_agent.queue.store import ActionStore

# Status strings returned by flow methods — checked by the Slack adapter to
# decide which message to post back.
NOT_AUTHORIZED = "not_authorized"
ALREADY_PROCESSED = "already_processed"
SENT = "sent"        # also used as "confirmed/executed" for calendar events
IGNORED = "ignored"
ERROR = "error"
AMBIGUOUS = "ambiguous"  # calendar event has unresolved fields; cannot create


class SendApprovalFlow:
    """Approve / ignore / edit-then-send for send_email PendingActions.

    All methods are idempotent: a second call on a non-pending action returns
    ALREADY_PROCESSED rather than calling send_email again (§4.5).
    Non-owner callers always get NOT_AUTHORIZED (§4.3).
    """

    def __init__(
        self, store: "ActionStore", agent: "Agent", owner_user_id: str
    ) -> None:
        self._store = store
        self._agent = agent
        self._owner_user_id = owner_user_id

    def approve(self, action_id: str, user_id: str) -> str:
        if not is_owner(user_id, self._owner_user_id):
            return NOT_AUTHORIZED
        if not self._store.is_pending(action_id):
            return ALREADY_PROCESSED
        row = self._store.get(action_id)
        try:
            self._agent.send_email(row["payload"])
        except Exception:
            return ERROR
        self._mark_source_processed(action_id, row["payload"])
        self._store.mark_sent(action_id)
        return SENT

    def ignore(self, action_id: str, user_id: str) -> str:
        if not is_owner(user_id, self._owner_user_id):
            return NOT_AUTHORIZED
        if not self._store.is_pending(action_id):
            return ALREADY_PROCESSED
        self._store.mark_ignored(action_id)
        return IGNORED

    def edit_and_send(self, action_id: str, user_id: str, new_body: str) -> str:
        if not is_owner(user_id, self._owner_user_id):
            return NOT_AUTHORIZED
        if not self._store.is_pending(action_id):
            return ALREADY_PROCESSED
        row = self._store.get(action_id)
        updated_payload = {**row["payload"], "body": new_body}
        try:
            self._agent.send_email(updated_payload)
        except Exception:
            return ERROR
        self._mark_source_processed(action_id, updated_payload)
        self._store.update_payload(action_id, updated_payload)
        self._store.mark_sent(action_id)
        return SENT

    def _mark_source_processed(
        self, action_id: str, payload: "dict[str, Any]"
    ) -> None:
        src = payload.get("source_message_id")
        if src:
            self._store.mark_message_processed(src, "send_email", action_id)


class CalendarApprovalFlow:
    """Confirm / dismiss for create_event PendingActions.

    Confirm is blocked if the payload has non-empty ambiguous_fields — the
    same guard the CLI applies (interfaces/cli.py). This is belt-and-suspenders:
    the Slack Block Kit for ambiguous events shows no Confirm button at all.
    """

    def __init__(
        self, store: "ActionStore", agent: "Agent", owner_user_id: str
    ) -> None:
        self._store = store
        self._agent = agent
        self._owner_user_id = owner_user_id

    def confirm(self, action_id: str, user_id: str) -> str:
        if not is_owner(user_id, self._owner_user_id):
            return NOT_AUTHORIZED
        if not self._store.is_pending(action_id):
            return ALREADY_PROCESSED
        row = self._store.get(action_id)
        if row["payload"].get("ambiguous_fields"):
            return AMBIGUOUS
        try:
            self._agent.create_event(row["payload"])
        except Exception:
            return ERROR
        self._store.mark_sent(action_id)
        return SENT

    def dismiss(self, action_id: str, user_id: str) -> str:
        if not is_owner(user_id, self._owner_user_id):
            return NOT_AUTHORIZED
        if not self._store.is_pending(action_id):
            return ALREADY_PROCESSED
        self._store.mark_ignored(action_id)
        return IGNORED


def pack_modal_metadata(action_id: str, channel: str, ts: str) -> str:
    """Encode action_id + channel + ts into the modal's private_metadata."""
    return json.dumps({"action_id": action_id, "channel": channel, "ts": ts})


def unpack_modal_metadata(private_metadata: str) -> dict[str, Any]:
    return json.loads(private_metadata)
