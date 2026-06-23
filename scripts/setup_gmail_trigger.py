"""Enable the GMAIL_NEW_EMAIL_TRIGGER on Composio for the configured user.

Run this ONCE before starting the app. After enabling the trigger, the
GmailWatcher in triggers/gmail_watch.py will receive events on new emails.

Usage:
    python scripts/setup_gmail_trigger.py
"""

from __future__ import annotations

import sys

from composio import Composio

from config.settings import load_settings

TRIGGER_NAME = "GMAIL_NEW_EMAIL_TRIGGER"


def main() -> None:
    settings = load_settings()
    composio = Composio(api_key=settings.composio_api_key)
    user_id = settings.composio_user_id

    print(f"Enabling {TRIGGER_NAME} for user '{user_id}'...")

    try:
        # Resolve the connected account for Gmail.
        accounts = composio.connected_accounts.get(user_id=user_id)
        gmail_account = next(
            (a for a in accounts if "gmail" in a.app_name.lower()),
            None,
        )
        if gmail_account is None:
            print(
                "ERROR: No Gmail connected account found for this user.\n"
                "Run: python scripts/connect_account.py gmail"
            )
            sys.exit(1)

        composio.triggers.enable(
            trigger_name=TRIGGER_NAME,
            connected_account_id=gmail_account.id,
            config={},
        )
        print(f"Trigger enabled. The app will now receive events on new emails.")
    except Exception as exc:
        print(f"ERROR: {exc}")
        print(
            "Note: the exact Composio API for enabling triggers may differ from the above.\n"
            "Check the Composio dashboard > Triggers to enable GMAIL_NEW_EMAIL_TRIGGER manually."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
