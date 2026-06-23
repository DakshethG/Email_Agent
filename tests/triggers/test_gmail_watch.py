"""Tests for GmailWatcher business logic.

_process_event() is tested in isolation via direct injection of fakes —
no real Composio trigger subscription or Slack API calls required.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from email_agent.core.models import AgentResult, Command, PendingAction
from email_agent.queue.store import ActionStore
from email_agent.triggers.gmail_watch import TRIGGER_NAME, GmailWatcher

OWNER_CHANNEL = "UOWNER123"


@pytest.fixture
def store(tmp_path) -> ActionStore:
    return ActionStore(tmp_path / "test.db")


def _make_watcher(
    agent: MagicMock,
    store: ActionStore,
    slack_client: MagicMock | None = None,
) -> GmailWatcher:
    """Build a GmailWatcher with mocked external clients."""
    watcher = GmailWatcher.__new__(GmailWatcher)
    watcher._agent = agent
    watcher._store = store
    watcher._composio = MagicMock()
    watcher._slack = slack_client or MagicMock()
    watcher._owner_channel = OWNER_CHANNEL
    return watcher


# --------------------------------------------------------------- _process_event


def test_new_email_calls_agent_and_posts_summary(store: ActionStore) -> None:
    """A trigger event runs agent.handle() and posts the summary to Slack DM."""
    mock_agent = MagicMock()
    mock_agent.handle.return_value = AgentResult(text="Email summary.", pending_actions=[])
    mock_slack = MagicMock()

    watcher = _make_watcher(mock_agent, store, slack_client=mock_slack)
    watcher._process_event({"threadId": "thread_1", "messageId": "msg_1"})

    mock_agent.handle.assert_called_once()
    cmd: Command = mock_agent.handle.call_args[0][0]
    assert "thread_1" in cmd.text

    mock_slack.chat_postMessage.assert_called_once()
    post_kwargs = mock_slack.chat_postMessage.call_args[1]
    assert post_kwargs["channel"] == OWNER_CHANNEL
    assert "Email summary." in post_kwargs["text"]


def test_duplicate_message_id_skips_agent(store: ActionStore) -> None:
    """A message already triggered does not cause agent.handle() to be called."""
    store.mark_message_processed("msg_seen", "auto_trigger", "auto_trigger")

    mock_agent = MagicMock()
    watcher = _make_watcher(mock_agent, store)
    watcher._process_event({"threadId": "thread_1", "messageId": "msg_seen"})

    mock_agent.handle.assert_not_called()


def test_missing_thread_id_skips_agent(store: ActionStore) -> None:
    """Events without a threadId are silently skipped."""
    mock_agent = MagicMock()
    watcher = _make_watcher(mock_agent, store)
    watcher._process_event({"messageId": "msg_no_thread"})

    mock_agent.handle.assert_not_called()


def test_pending_reply_posted_with_approval_blocks(store: ActionStore) -> None:
    """A send_email PendingAction is stored and posted via Block Kit."""
    mock_agent = MagicMock()
    mock_agent.handle.return_value = AgentResult(
        text="New email from Alice.",
        pending_actions=[
            PendingAction(
                type="send_email",
                payload={
                    "thread_id": "t2",
                    "recipient_email": "alice@example.com",
                    "body": "Thanks!",
                    "source_message_id": "msg_2",
                },
            )
        ],
    )
    mock_slack = MagicMock()

    watcher = _make_watcher(mock_agent, store, slack_client=mock_slack)
    watcher._process_event({"threadId": "t2", "messageId": "msg_2"})

    # Summary post + action block post = 2 calls.
    assert mock_slack.chat_postMessage.call_count == 2
    block_calls = [c for c in mock_slack.chat_postMessage.call_args_list if "blocks" in c[1]]
    assert len(block_calls) == 1
    assert block_calls[0][1]["channel"] == OWNER_CHANNEL


def test_pending_event_posted_with_approval_blocks(store: ActionStore) -> None:
    """A create_event PendingAction is stored and posted via Block Kit."""
    mock_agent = MagicMock()
    mock_agent.handle.return_value = AgentResult(
        text="Meeting found.",
        pending_actions=[
            PendingAction(
                type="create_event",
                payload={
                    "title": "Team Sync",
                    "start": "2026-06-22T10:00:00",
                    "end": "2026-06-22T11:00:00",
                    "timezone": "UTC",
                    "location": None,
                    "attendees": [],
                    "description": None,
                    "ambiguous_fields": [],
                },
            )
        ],
    )
    mock_slack = MagicMock()

    watcher = _make_watcher(mock_agent, store, slack_client=mock_slack)
    watcher._process_event({"threadId": "t3", "messageId": "msg_3"})

    block_calls = [c for c in mock_slack.chat_postMessage.call_args_list if "blocks" in c[1]]
    assert len(block_calls) == 1
    assert block_calls[0][1]["channel"] == OWNER_CHANNEL


def test_duplicate_reply_from_trigger_is_skipped(store: ActionStore) -> None:
    """If a reply was already sent for source_message_id, no new block is posted."""
    existing_id = store.add("send_email", {"body": "earlier reply"})
    store.mark_message_processed("msg_4", "send_email", existing_id)

    mock_agent = MagicMock()
    mock_agent.handle.return_value = AgentResult(
        text="Summary.",
        pending_actions=[
            PendingAction(
                type="send_email",
                payload={
                    "thread_id": "t4",
                    "recipient_email": "bob@example.com",
                    "body": "New reply attempt",
                    "source_message_id": "msg_4",
                },
            )
        ],
    )
    mock_slack = MagicMock()

    watcher = _make_watcher(mock_agent, store, slack_client=mock_slack)
    watcher._process_event({"threadId": "t4", "messageId": "msg_4_trigger"})

    # Only the summary post should go out — no block for the duplicate reply.
    block_calls = [c for c in mock_slack.chat_postMessage.call_args_list if "blocks" in c[1]]
    assert block_calls == [], "Duplicate reply should not produce an approval block"


def test_composed_result_posts_both_reply_and_event_blocks(store: ActionStore) -> None:
    """A composed result with both a reply and an event proposal posts two blocks."""
    mock_agent = MagicMock()
    mock_agent.handle.return_value = AgentResult(
        text="Email about a meeting.",
        pending_actions=[
            PendingAction(
                type="send_email",
                payload={
                    "thread_id": "t5",
                    "recipient_email": "carol@example.com",
                    "body": "I'll be there.",
                    "source_message_id": "msg_5",
                },
            ),
            PendingAction(
                type="create_event",
                payload={
                    "title": "Catch-up",
                    "start": "2026-07-01T14:00:00",
                    "end": "2026-07-01T15:00:00",
                    "timezone": "UTC",
                    "location": None,
                    "attendees": ["carol@example.com"],
                    "description": None,
                    "ambiguous_fields": [],
                },
            ),
        ],
    )
    mock_slack = MagicMock()

    watcher = _make_watcher(mock_agent, store, slack_client=mock_slack)
    watcher._process_event({"threadId": "t5", "messageId": "msg_5"})

    # Summary + reply block + event block = 3 calls.
    assert mock_slack.chat_postMessage.call_count == 3
    block_calls = [c for c in mock_slack.chat_postMessage.call_args_list if "blocks" in c[1]]
    assert len(block_calls) == 2
