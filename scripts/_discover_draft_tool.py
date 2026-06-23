"""One-off discovery (NOT part of the app): find the Gmail draft-creation
tool slug + schema via Composio, per CLAUDE.md §6 (verify live, don't
hardcode). Deleted after use.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from composio import Composio

from config.settings import load_settings

settings = load_settings()
composio = Composio(api_key=settings.composio_api_key)

print("--- GMAIL_CREATE_EMAIL_DRAFT schema ---")
tools = composio.tools.get(user_id=settings.composio_user_id, tools=["GMAIL_CREATE_EMAIL_DRAFT"])
import json
print(json.dumps(tools[0]["function"]["parameters"], indent=2))
