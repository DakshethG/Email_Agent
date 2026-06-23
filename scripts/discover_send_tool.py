"""Discover and verify the Composio slug for sending/replying to a Gmail email.

Run: python scripts/discover_send_tool.py

Checks several candidate slugs and prints their parameter schemas so the
correct one can be confirmed before Phase 4 end-to-end use.
Per CLAUDE.md §6 — always verify live; never hardcode from memory.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from composio import Composio

from config.settings import load_settings

settings = load_settings()
composio = Composio(api_key=settings.composio_api_key)

CANDIDATES = [
    "GMAIL_SEND_EMAIL",
    "GMAIL_REPLY_TO_EMAIL",
    "GMAIL_REPLY_TO_THREAD",
    "GMAIL_SEND_MESSAGE",
]

for slug in CANDIDATES:
    try:
        tools = composio.tools.get(user_id=settings.composio_user_id, tools=[slug])
        if tools:
            print(f"\n=== {slug} (FOUND) ===")
            print(json.dumps(tools[0]["function"]["parameters"], indent=2))
        else:
            print(f"\n--- {slug}: not found ---")
    except Exception as exc:
        print(f"\n--- {slug}: error — {exc} ---")

print("\n\nDone. Update SEND_EMAIL_SLUG in src/email_agent/tools/gmail.py to the")
print("confirmed slug, then update build_send_email_arguments() to match its schema.")
