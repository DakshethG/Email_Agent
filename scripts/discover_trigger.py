"""List available Composio trigger names for Gmail.

Useful for discovering the exact trigger slug before wiring up
triggers/gmail_watch.py. Run this against your Composio account to see
what's available.

Usage:
    python scripts/discover_trigger.py
"""

from __future__ import annotations

from composio import Composio

from config.settings import load_settings


def main() -> None:
    settings = load_settings()
    composio = Composio(api_key=settings.composio_api_key)

    print("Fetching available triggers for GMAIL toolkit...\n")
    try:
        triggers = composio.triggers.get(app_name="gmail")
        if not triggers:
            print("No triggers found. Check Composio dashboard.")
            return
        for t in triggers:
            name = getattr(t, "trigger_name", None) or getattr(t, "name", str(t))
            desc = getattr(t, "description", "")
            print(f"  {name}: {desc}")
    except Exception as exc:
        print(f"ERROR fetching triggers: {exc}")
        print(
            "Try listing triggers on the Composio dashboard directly:\n"
            "  https://app.composio.dev/app/gmail → Triggers tab"
        )


if __name__ == "__main__":
    main()
