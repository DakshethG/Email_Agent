"""Phase 0 smoke test: Slack Bolt, Socket Mode.

Connects via Socket Mode, then waits for one direct message from the
configured owner and echoes it back. Proves SLACK_BOT_TOKEN /
SLACK_APP_TOKEN / SLACK_OWNER_USER_ID are correct and Socket Mode works.

Before running, in your Slack app config:
- Enable Socket Mode and generate an App-Level Token with `connections:write`
  (this is SLACK_APP_TOKEN, starts with xapp-).
- Add bot scope `chat:write` and subscribe to the `message.im` event.
- Install the app to your workspace (SLACK_BOT_TOKEN starts with xoxb-).

Run:
    python scripts/smoke_slack.py
Then send the bot a DM from the owner account.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config.settings import MissingEnvVar, load_settings

WAIT_TIMEOUT_SECONDS = 120


def main() -> int:
    try:
        settings = load_settings()
    except MissingEnvVar as exc:
        print(f"FAIL: {exc}")
        return 1

    app = App(token=settings.slack_bot_token)
    done = threading.Event()
    outcome = {"passed": False}

    @app.event("message")
    def handle_message(event, say, logger):
        if done.is_set():
            return
        user = event.get("user")
        text = event.get("text", "")
        if user != settings.slack_owner_user_id:
            logger.info("Ignoring message from non-owner user %r", user)
            return
        say(f"echo: {text}")
        outcome["passed"] = True
        done.set()

    handler = SocketModeHandler(app, settings.slack_app_token)

    try:
        handler.connect()
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: Socket Mode connection raised: {exc}")
        return 1

    print("Connected via Socket Mode.")
    print(
        f"Send a Slack DM to the bot from owner user {settings.slack_owner_user_id!r} "
        f"within {WAIT_TIMEOUT_SECONDS}s..."
    )

    received = done.wait(timeout=WAIT_TIMEOUT_SECONDS)
    handler.close()

    if not received or not outcome["passed"]:
        print(f"FAIL: no message received from owner within {WAIT_TIMEOUT_SECONDS}s")
        return 1

    print("PASS: smoke_slack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
