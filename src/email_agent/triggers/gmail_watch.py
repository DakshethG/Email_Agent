"""Real-time Gmail trigger via Composio's trigger subscription system.

GmailWatcher subscribes to GMAIL_NEW_EMAIL_TRIGGER events via Composio's
long-poll listener (no public URL required). On each new email it:
  1. Checks idempotency — skips messages already triggered.
  2. Calls agent.handle() with a composed command (summarize + propose event
     and/or reply).
  3. Posts the summary text to the owner's Slack DM.
  4. Posts any pending_actions (replies, events) through the Phase 4 approval
     gate — no new send path (CLAUDE.md §4.1).

Setup: run `python scripts/setup_gmail_trigger.py` once to enable the trigger
on Composio before starting the app.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from composio import Composio
from slack_sdk import WebClient

from config.settings import Settings
from email_agent.core.agent import Agent
from email_agent.core.models import Command
from email_agent.interfaces.blocks import create_event_blocks, send_email_blocks
from email_agent.queue.store import ActionStore

logger = logging.getLogger(__name__)

TRIGGER_NAME = "GMAIL_NEW_EMAIL_TRIGGER"
_TRIGGER_ACTION_ID = "auto_trigger"


class GmailWatcher:
    """Listens for new Gmail messages and runs the agent pipeline on each one.

    Constructor dependencies are injectable for testing. In production, pass
    only `agent`, `store`, and `settings` — the Composio and Slack clients are
    created automatically from settings.
    """

    def __init__(
        self,
        agent: Agent,
        store: ActionStore,
        settings: Settings,
        _composio: Composio | None = None,
        _slack_client: WebClient | None = None,
    ) -> None:
        self._agent = agent
        self._store = store
        self._composio = _composio or Composio(api_key=settings.composio_api_key)
        self._slack = _slack_client or WebClient(token=settings.slack_bot_token)
        self._owner_channel = settings.slack_owner_user_id

    def start(self) -> None:
        """Start the Composio trigger listener (blocking call).

        Wraps start_background() — call this directly only if you manage the
        thread yourself. In production, prefer start_background().
        """
        try:
            listener = self._composio.triggers.subscribe()

            @listener.callback(filters={"triggerName": TRIGGER_NAME})
            def on_trigger(event: Any) -> None:
                try:
                    self._process_event(event.payload)
                except Exception:
                    logger.exception("Error processing Gmail trigger event")

            logger.info("Gmail trigger listener started, watching %s", TRIGGER_NAME)
            listener.listen()
        except AttributeError:
            logger.error(
                "Composio trigger subscription API unavailable. "
                "Verify SDK version and run `python scripts/setup_gmail_trigger.py`."
            )
        except Exception:
            logger.exception("Gmail trigger listener failed")

    def start_background(self) -> threading.Thread:
        """Start the trigger listener in a daemon thread (non-blocking)."""
        thread = threading.Thread(target=self.start, daemon=True, name="gmail-watcher")
        thread.start()
        return thread

    def _process_event(self, payload: dict[str, Any]) -> None:
        """Handle one new-email event.

        This is the business-logic entry point — call it directly in tests
        with a fake payload dict.
        """
        message_id: str = payload.get("messageId") or payload.get("message_id") or ""
        thread_id: str = payload.get("threadId") or payload.get("thread_id") or ""

        if not thread_id:
            logger.warning("Trigger payload missing threadId, skipping: %s", payload)
            return

        # Idempotency: skip if we already triggered on this message.
        if message_id and self._store.is_message_processed(message_id, "auto_trigger"):
            logger.info("Already triggered on message %s, skipping", message_id)
            return

        command_text = (
            f"New email received in thread {thread_id}. "
            "Please: 1) summarize it, "
            "2) if it mentions a meeting or appointment, propose a calendar event, "
            "3) if a reply seems appropriate, propose one for my approval."
        )
        result = self._agent.handle(Command(text=command_text))

        if result.text:
            self._slack.chat_postMessage(
                channel=self._owner_channel,
                text=f"*New email*\n{result.text}",
            )

        for action in result.pending_actions:
            self._post_pending_action(action, source_message_id=message_id)

        # Mark this message so we don't re-trigger it.
        # SQLite does not enforce the FK by default; the sentinel action_id is safe.
        if message_id:
            self._store.mark_message_processed(message_id, "auto_trigger", _TRIGGER_ACTION_ID)

    def _post_pending_action(self, action: Any, source_message_id: str) -> None:
        """Post one pending action to the owner's DM via the existing approval gate."""
        if action.type == "send_email":
            payload = action.payload
            # Inject source_message_id if the model omitted it.
            if source_message_id and not payload.get("source_message_id"):
                payload = {**payload, "source_message_id": source_message_id}
            # Skip if a reply already exists for this source message.
            src = payload.get("source_message_id")
            if src and self._store.is_message_processed(src, "send_email"):
                logger.info("Reply already exists for message %s, skipping", src)
                return
            action_id = self._store.add("send_email", payload)
            self._slack.chat_postMessage(
                channel=self._owner_channel,
                blocks=send_email_blocks(action_id, payload),
                text="Proposed reply — approve via buttons.",
            )
        elif action.type == "create_event":
            action_id = self._store.add("create_event", action.payload)
            self._slack.chat_postMessage(
                channel=self._owner_channel,
                blocks=create_event_blocks(action_id, action.payload),
                text="Proposed calendar event — approve via buttons.",
            )
        else:
            logger.warning("Unknown pending action type from trigger: %s", action.type)
