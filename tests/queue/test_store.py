"""Tests for queue/store.py — SQLite pending-action store."""

from __future__ import annotations

import pytest

from email_agent.queue.store import ActionStore

_PAYLOAD = {"thread_id": "t1", "recipient_email": "alice@example.com", "body": "Hello!"}


@pytest.fixture
def store(tmp_path) -> ActionStore:
    return ActionStore(tmp_path / "test.db")


def test_add_and_get(store: ActionStore) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    row = store.get(action_id)
    assert row is not None
    assert row["action_id"] == action_id
    assert row["type"] == "send_email"
    assert row["payload"] == _PAYLOAD
    assert row["status"] == "pending"


def test_is_pending_new_action(store: ActionStore) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    assert store.is_pending(action_id)


def test_mark_sent(store: ActionStore) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    store.mark_sent(action_id)
    assert not store.is_pending(action_id)
    assert store.get(action_id)["status"] == "sent"


def test_mark_ignored(store: ActionStore) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    store.mark_ignored(action_id)
    assert not store.is_pending(action_id)
    assert store.get(action_id)["status"] == "ignored"


def test_update_payload(store: ActionStore) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    new_payload = {**_PAYLOAD, "body": "Edited reply."}
    store.update_payload(action_id, new_payload)
    assert store.get(action_id)["payload"]["body"] == "Edited reply."


def test_double_mark_sent_is_idempotent(store: ActionStore) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    store.mark_sent(action_id)
    store.mark_sent(action_id)
    assert store.get(action_id)["status"] == "sent"


def test_get_nonexistent_returns_none(store: ActionStore) -> None:
    assert store.get("no-such-id") is None


def test_is_pending_nonexistent_returns_false(store: ActionStore) -> None:
    assert not store.is_pending("no-such-id")


def test_multiple_actions_are_independent(store: ActionStore) -> None:
    id1 = store.add("send_email", {"body": "first"})
    id2 = store.add("send_email", {"body": "second"})
    store.mark_sent(id1)
    assert not store.is_pending(id1)
    assert store.is_pending(id2)


# --------------------------------------------------------- message-ID idempotency

def test_mark_and_check_message_processed(store: ActionStore) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    store.mark_message_processed("gmail_msg_1", "send_email", action_id)
    assert store.is_message_processed("gmail_msg_1", "send_email")


def test_unprocessed_message_returns_false(store: ActionStore) -> None:
    assert not store.is_message_processed("gmail_msg_unseen", "send_email")


def test_message_processed_is_action_type_scoped(store: ActionStore) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    store.mark_message_processed("gmail_msg_1", "send_email", action_id)
    # Same message_id but different action_type is NOT considered processed.
    assert not store.is_message_processed("gmail_msg_1", "create_event")


def test_duplicate_mark_message_processed_is_idempotent(store: ActionStore) -> None:
    action_id = store.add("send_email", _PAYLOAD)
    store.mark_message_processed("gmail_msg_1", "send_email", action_id)
    store.mark_message_processed("gmail_msg_1", "send_email", action_id)  # second call
    assert store.is_message_processed("gmail_msg_1", "send_email")
