"""Tests for the send-email and calendar-event approval flows.

Tests business logic in isolation — no real Slack API calls needed.
send_email: approve sends once, ignore sends nothing, edit sends modified text,
            non-owner rejected, double-approval does not double-send.
create_event: confirm creates event, dismiss discards, ambiguous fields blocked,
              non-owner rejected, idempotency.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from email_agent.interfaces.approval_handlers import (
    ALREADY_PROCESSED,
    AMBIGUOUS,
    IGNORED,
    NOT_AUTHORIZED,
    SENT,
    CalendarApprovalFlow,
    SendApprovalFlow,
)
from email_agent.queue.store import ActionStore

OWNER_ID = "UOWNER123"
OTHER_ID = "UOTHER456"
_PAYLOAD = {
    "thread_id": "thread_abc",
    "recipient_email": "alice@example.com",
    "body": "Hello, Alice!",
}


@pytest.fixture
def store(tmp_path) -> ActionStore:
    return ActionStore(tmp_path / "test.db")


@pytest.fixture
def mock_agent() -> MagicMock:
    agent = MagicMock()
    agent.send_email.return_value = {"successful": True}
    return agent


@pytest.fixture
def flow(store, mock_agent) -> SendApprovalFlow:
    return SendApprovalFlow(store, mock_agent, OWNER_ID)


# ----------------------------------------------------------- approve

def test_approve_sends_email_and_marks_sent(store, mock_agent, flow) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    result = flow.approve(action_id, OWNER_ID)
    assert result == SENT
    mock_agent.send_email.assert_called_once_with(_PAYLOAD)
    assert store.get(action_id)["status"] == "sent"
    assert not store.is_pending(action_id)


def test_approve_non_owner_rejected(store, mock_agent, flow) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    result = flow.approve(action_id, OTHER_ID)
    assert result == NOT_AUTHORIZED
    mock_agent.send_email.assert_not_called()
    assert store.is_pending(action_id)


def test_double_approve_does_not_double_send(store, mock_agent, flow) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    first = flow.approve(action_id, OWNER_ID)
    second = flow.approve(action_id, OWNER_ID)
    assert first == SENT
    assert second == ALREADY_PROCESSED
    mock_agent.send_email.assert_called_once()


def test_approve_already_ignored_returns_already_processed(store, mock_agent, flow) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    flow.ignore(action_id, OWNER_ID)
    result = flow.approve(action_id, OWNER_ID)
    assert result == ALREADY_PROCESSED
    mock_agent.send_email.assert_not_called()


# ----------------------------------------------------------- ignore

def test_ignore_marks_ignored_and_does_not_send(store, mock_agent, flow) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    result = flow.ignore(action_id, OWNER_ID)
    assert result == IGNORED
    mock_agent.send_email.assert_not_called()
    assert store.get(action_id)["status"] == "ignored"


def test_ignore_non_owner_rejected(store, mock_agent, flow) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    result = flow.ignore(action_id, OTHER_ID)
    assert result == NOT_AUTHORIZED
    assert store.is_pending(action_id)


def test_double_ignore_returns_already_processed(store, mock_agent, flow) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    flow.ignore(action_id, OWNER_ID)
    result = flow.ignore(action_id, OWNER_ID)
    assert result == ALREADY_PROCESSED


# ----------------------------------------------------------- edit and send

def test_edit_and_send_uses_edited_body(store, mock_agent, flow) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    result = flow.edit_and_send(action_id, OWNER_ID, "Edited reply text.")
    assert result == SENT
    call_payload = mock_agent.send_email.call_args[0][0]
    assert call_payload["body"] == "Edited reply text."
    assert call_payload["thread_id"] == "thread_abc"
    assert call_payload["recipient_email"] == "alice@example.com"
    assert store.get(action_id)["status"] == "sent"
    assert store.get(action_id)["payload"]["body"] == "Edited reply text."


def test_edit_non_owner_rejected(store, mock_agent, flow) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    result = flow.edit_and_send(action_id, OTHER_ID, "bad edit")
    assert result == NOT_AUTHORIZED
    mock_agent.send_email.assert_not_called()


def test_edit_after_sent_returns_already_processed(store, mock_agent, flow) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    flow.approve(action_id, OWNER_ID)
    result = flow.edit_and_send(action_id, OWNER_ID, "too late")
    assert result == ALREADY_PROCESSED
    mock_agent.send_email.assert_called_once()


# ================================================================ CalendarApprovalFlow

_EVENT_PAYLOAD = {
    "title": "Team Sync",
    "start": "2026-06-22T10:00:00",
    "end": "2026-06-22T11:00:00",
    "timezone": "America/New_York",
    "location": "Room A",
    "attendees": ["alice@example.com"],
    "description": None,
    "ambiguous_fields": [],
}

_AMBIGUOUS_EVENT_PAYLOAD = {
    **_EVENT_PAYLOAD,
    "start": None,
    "end": None,
    "ambiguous_fields": ["start", "end"],
}


@pytest.fixture
def cal_flow(store, mock_agent) -> CalendarApprovalFlow:
    return CalendarApprovalFlow(store, mock_agent, OWNER_ID)


def test_confirm_creates_event_and_marks_sent(store, mock_agent, cal_flow) -> None:
    mock_agent.create_event.return_value = {"successful": True}
    action_id = store.add("create_event", _EVENT_PAYLOAD)
    result = cal_flow.confirm(action_id, OWNER_ID)
    assert result == SENT
    mock_agent.create_event.assert_called_once_with(_EVENT_PAYLOAD)
    assert store.get(action_id)["status"] == "sent"


def test_confirm_non_owner_rejected(store, mock_agent, cal_flow) -> None:
    action_id = store.add("create_event", _EVENT_PAYLOAD)
    result = cal_flow.confirm(action_id, OTHER_ID)
    assert result == NOT_AUTHORIZED
    mock_agent.create_event.assert_not_called()
    assert store.is_pending(action_id)


def test_confirm_ambiguous_event_blocked(store, mock_agent, cal_flow) -> None:
    action_id = store.add("create_event", _AMBIGUOUS_EVENT_PAYLOAD)
    result = cal_flow.confirm(action_id, OWNER_ID)
    assert result == AMBIGUOUS
    mock_agent.create_event.assert_not_called()
    assert store.is_pending(action_id)


def test_double_confirm_does_not_double_create(store, mock_agent, cal_flow) -> None:
    mock_agent.create_event.return_value = {"successful": True}
    action_id = store.add("create_event", _EVENT_PAYLOAD)
    first = cal_flow.confirm(action_id, OWNER_ID)
    second = cal_flow.confirm(action_id, OWNER_ID)
    assert first == SENT
    assert second == ALREADY_PROCESSED
    mock_agent.create_event.assert_called_once()


def test_dismiss_marks_ignored_no_event_created(store, mock_agent, cal_flow) -> None:
    action_id = store.add("create_event", _EVENT_PAYLOAD)
    result = cal_flow.dismiss(action_id, OWNER_ID)
    assert result == IGNORED
    mock_agent.create_event.assert_not_called()
    assert store.get(action_id)["status"] == "ignored"


def test_dismiss_non_owner_rejected(store, mock_agent, cal_flow) -> None:
    action_id = store.add("create_event", _EVENT_PAYLOAD)
    result = cal_flow.dismiss(action_id, OTHER_ID)
    assert result == NOT_AUTHORIZED
    assert store.is_pending(action_id)


def test_confirm_after_dismiss_returns_already_processed(store, mock_agent, cal_flow) -> None:
    action_id = store.add("create_event", _EVENT_PAYLOAD)
    cal_flow.dismiss(action_id, OWNER_ID)
    result = cal_flow.confirm(action_id, OWNER_ID)
    assert result == ALREADY_PROCESSED
    mock_agent.create_event.assert_not_called()


# ============================================================ idempotency / Phase 5

def test_approve_marks_source_message_processed(store, mock_agent, flow) -> None:
    payload_with_source = {**_PAYLOAD, "source_message_id": "gmail_msg_1"}
    action_id = store.add("send_email", payload_with_source)
    flow.approve(action_id, OWNER_ID)
    assert store.is_message_processed("gmail_msg_1", "send_email")


def test_edit_and_send_marks_source_message_processed(store, mock_agent, flow) -> None:
    payload_with_source = {**_PAYLOAD, "source_message_id": "gmail_msg_2"}
    action_id = store.add("send_email", payload_with_source)
    flow.edit_and_send(action_id, OWNER_ID, "Edited body.")
    assert store.is_message_processed("gmail_msg_2", "send_email")


def test_approve_without_source_message_id_still_works(store, mock_agent, flow) -> None:
    action_id = store.add("send_email", _PAYLOAD)  # no source_message_id
    result = flow.approve(action_id, OWNER_ID)
    assert result == SENT  # no crash, no idempotency record needed
