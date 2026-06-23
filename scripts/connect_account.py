"""One-time setup helper: connect a Google/Slack account to Composio.

Creates (or reuses) an auth config for the given toolkit using Composio's
managed OAuth app, prints a link for the owner to authorize, and waits for
the connection to become active.

Run:
    python scripts/connect_account.py gmail
    python scripts/connect_account.py googlecalendar
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from composio import Composio

from config.settings import MissingEnvVar, load_settings

COMPOSIO_USER_ID = "default"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/connect_account.py <toolkit_slug>")
        print("Example: python scripts/connect_account.py gmail")
        return 1

    toolkit = sys.argv[1].lower()

    try:
        settings = load_settings()
    except MissingEnvVar as exc:
        print(f"FAIL: {exc}")
        return 1

    composio = Composio(api_key=settings.composio_api_key)

    existing = composio.auth_configs.list(toolkit_slug=toolkit)
    if existing.items:
        auth_config_id = existing.items[0].id
        print(f"Using existing auth config {auth_config_id} for toolkit {toolkit!r}")
    else:
        created = composio.auth_configs.create(
            toolkit, {"type": "use_composio_managed_auth"}
        )
        auth_config_id = created.id
        print(f"Created auth config {auth_config_id} for toolkit {toolkit!r}")

    connection_request = composio.connected_accounts.link(
        user_id=COMPOSIO_USER_ID,
        auth_config_id=auth_config_id,
    )

    print(f"Visit this URL to authorize ({toolkit}):")
    print(connection_request.redirect_url)
    print("Waiting for authorization (up to 5 minutes)...")

    try:
        connected_account = connection_request.wait_for_connection(timeout=300)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: did not become active: {exc}")
        return 1

    print(f"PASS: connected account {connected_account.id} is active for {toolkit!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
