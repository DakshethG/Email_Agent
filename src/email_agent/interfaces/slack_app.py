"""Slack adapter: Bolt app over Socket Mode.

Per CLAUDE.md §3 / §4.3: Slack is an *interface*, not a model tool. It only
receives commands from the configured owner, forwards them to
`agent.handle()`, and posts the resulting text back. The model never posts to
Slack itself.

Phase 4 additions: Block Kit approval messages (Send / Edit / Ignore) for
`send_email` PendingActions, and (Confirm / Dismiss) for `create_event`
PendingActions. The SQLite queue is the source of truth; Slack just surfaces
it. All action handlers ack() immediately, then do slow work (Slack's 3-second
ack window).

Phase 6 additions: GmailWatcher started as a background thread on startup.
Summary-only commands are routed to the cheaper fallback NIM model.

Run with: python -m email_agent.interfaces.slack_app
"""

from __future__ import annotations

import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config.settings import load_settings
from email_agent.core.agent import Agent
from email_agent.core.models import Command
from email_agent.interfaces.approval_handlers import (
    ALREADY_PROCESSED,
    AMBIGUOUS,
    ERROR,
    IGNORED,
    NOT_AUTHORIZED,
    SENT,
    CalendarApprovalFlow,
    SendApprovalFlow,
    pack_modal_metadata,
    unpack_modal_metadata,
)
from email_agent.interfaces.blocks import (
    CALENDAR_TERMINAL,
    EMAIL_TERMINAL,
    create_event_blocks,
    send_email_blocks,
)
from email_agent.queue.store import ActionStore
from email_agent.safety.guards import is_owner

logger = logging.getLogger(__name__)

# Keep underscore-prefixed aliases so any existing callers (tests etc.) still work.
_send_email_blocks = send_email_blocks
_create_event_blocks = create_event_blocks
_EMAIL_TERMINAL = EMAIL_TERMINAL
_CALENDAR_TERMINAL = CALENDAR_TERMINAL


# ----------------------------------------------------------------- Block Kit


def _update_to_terminal(client, channel: str, ts: str, text: str) -> None:
    """Replace Block Kit buttons with a plain terminal status line."""
    client.chat_update(
        channel=channel,
        ts=ts,
        blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
        text=text,
    )


# ---------------------------------------------------------------- Fast-model routing


def _wants_fast_model(text: str) -> bool:
    """True for summary-only commands that don't need tool-capable model."""
    lowered = text.lower()
    has_summary = any(w in lowered for w in ("summarize", "summary", "tldr", "what's in"))
    has_action = any(
        w in lowered for w in ("reply", "respond", "send", "event", "meeting", "draft")
    )
    return has_summary and not has_action


# --------------------------------------------------------------- main / app


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    settings = load_settings()
    app = App(token=settings.slack_bot_token)
    agent = Agent(settings=settings)
    store = ActionStore(settings.pending_db_path)
    send_flow = SendApprovalFlow(store, agent, settings.slack_owner_user_id)
    cal_flow = CalendarApprovalFlow(store, agent, settings.slack_owner_user_id)

    # Start Gmail trigger watcher in a background daemon thread.
    try:
        from email_agent.triggers.gmail_watch import GmailWatcher

        watcher = GmailWatcher(agent=agent, store=store, settings=settings)
        watcher.start_background()
        logger.info("Gmail trigger watcher started")
    except Exception:
        logger.exception("Could not start Gmail trigger watcher — continuing without it")

    # ---------------------------------------------------------------- DM handler

    @app.event("message")
    def handle_message(event: dict, say) -> None:
        if event.get("channel_type") != "im" or "subtype" in event:
            return

        user_id = event.get("user")
        if not is_owner(user_id, settings.slack_owner_user_id):
            logger.info("Ignoring message from non-owner user %s", user_id)
            return

        text = event.get("text", "").strip()
        if not text:
            return

        use_fast = _wants_fast_model(text)
        result = agent.handle(Command(text=text), use_fast_model=use_fast)
        say(result.text)

        for action in result.pending_actions:
            if action.type == "send_email":
                # Idempotency: skip if this Gmail message was already replied to.
                src_id = action.payload.get("source_message_id")
                if src_id and store.is_message_processed(src_id, "send_email"):
                    say("↩️ Already replied to that email — skipping duplicate.")
                    continue
                action_id = store.add("send_email", action.payload)
                say(blocks=send_email_blocks(action_id, action.payload))
            elif action.type == "create_event":
                action_id = store.add("create_event", action.payload)
                say(blocks=create_event_blocks(action_id, action.payload))
            else:
                say(f"[pending action] {action.type}: {action.payload}")

    # ------------------------------------------------------------- Send button

    @app.action("approve_send")
    def handle_approve_send(ack, body, client) -> None:
        ack()
        action_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        channel = body["channel"]["id"]
        ts = body["message"]["ts"]

        status = send_flow.approve(action_id, user_id)
        if status != NOT_AUTHORIZED:
            _update_to_terminal(client, channel, ts, EMAIL_TERMINAL.get(status, status))
        else:
            logger.warning("Non-owner %s attempted to approve send %s", user_id, action_id)

    # --------------------------------------------------------------- Edit button

    @app.action("edit_send")
    def handle_edit_send(ack, body, client) -> None:
        ack()
        action_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        channel = body["channel"]["id"]
        ts = body["message"]["ts"]

        if not is_owner(user_id, settings.slack_owner_user_id):
            logger.warning("Non-owner %s attempted to edit send %s", user_id, action_id)
            return

        if not store.is_pending(action_id):
            _update_to_terminal(client, channel, ts, EMAIL_TERMINAL[ALREADY_PROCESSED])
            return

        row = store.get(action_id)
        current_body = row["payload"].get("body", "")

        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "edit_send_modal",
                "private_metadata": pack_modal_metadata(action_id, channel, ts),
                "title": {"type": "plain_text", "text": "Edit Reply"},
                "submit": {"type": "plain_text", "text": "Send"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "reply_body",
                        "label": {"type": "plain_text", "text": "Reply text"},
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "body_input",
                            "multiline": True,
                            "initial_value": current_body,
                        },
                    }
                ],
            },
        )

    # ------------------------------------------------------------ Modal submit

    @app.view("edit_send_modal")
    def handle_edit_send_modal(ack, body, client) -> None:
        ack()
        meta = unpack_modal_metadata(body["view"]["private_metadata"])
        action_id = meta["action_id"]
        channel = meta["channel"]
        ts = meta["ts"]
        user_id = body["user"]["id"]

        new_body = (
            body["view"]["state"]["values"]["reply_body"]["body_input"]["value"] or ""
        )

        status = send_flow.edit_and_send(action_id, user_id, new_body)
        if status != NOT_AUTHORIZED:
            _update_to_terminal(client, channel, ts, EMAIL_TERMINAL.get(status, status))
        else:
            logger.warning("Non-owner %s attempted modal send for %s", user_id, action_id)

    # ------------------------------------------------------------- Ignore button

    @app.action("ignore_send")
    def handle_ignore_send(ack, body, client) -> None:
        ack()
        action_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        channel = body["channel"]["id"]
        ts = body["message"]["ts"]

        status = send_flow.ignore(action_id, user_id)
        if status != NOT_AUTHORIZED:
            _update_to_terminal(client, channel, ts, EMAIL_TERMINAL.get(status, status))
        else:
            logger.warning("Non-owner %s attempted to ignore send %s", user_id, action_id)

    # --------------------------------------------------------- Confirm Event button

    @app.action("confirm_event")
    def handle_confirm_event(ack, body, client) -> None:
        ack()
        action_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        channel = body["channel"]["id"]
        ts = body["message"]["ts"]

        status = cal_flow.confirm(action_id, user_id)
        if status != NOT_AUTHORIZED:
            _update_to_terminal(client, channel, ts, CALENDAR_TERMINAL.get(status, status))
        else:
            logger.warning("Non-owner %s attempted to confirm event %s", user_id, action_id)

    # --------------------------------------------------------- Dismiss Event button

    @app.action("dismiss_event")
    def handle_dismiss_event(ack, body, client) -> None:
        ack()
        action_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        channel = body["channel"]["id"]
        ts = body["message"]["ts"]

        status = cal_flow.dismiss(action_id, user_id)
        if status != NOT_AUTHORIZED:
            _update_to_terminal(client, channel, ts, CALENDAR_TERMINAL.get(status, status))
        else:
            logger.warning("Non-owner %s attempted to dismiss event %s", user_id, action_id)

    # ------------------------------------------------------------------- start

    handler = SocketModeHandler(app, settings.slack_app_token)
    handler.start()


if __name__ == "__main__":
    main()
