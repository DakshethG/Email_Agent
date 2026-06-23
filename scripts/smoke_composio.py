"""Phase 0 smoke test: Composio auth + Gmail read access.

Verifies the Composio API key works and a GMAIL connected account exists for
the configured user, by listing a few recent Gmail messages.

Before running, connect a Gmail account for COMPOSIO_USER_ID via:
    composio.connected_accounts.link(user_id=COMPOSIO_USER_ID, auth_config_id=...)
(create the auth config on https://dashboard.composio.dev first, then visit
the printed redirect_url to complete OAuth).

Run:
    python scripts/smoke_composio.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from composio import Composio

from config.settings import MissingEnvVar, load_settings

# Single personal user — see docs/phase0.md.
COMPOSIO_USER_ID = "default"


def main() -> int:
    try:
        settings = load_settings()
    except MissingEnvVar as exc:
        print(f"FAIL: {exc}")
        return 1

    composio = Composio(api_key=settings.composio_api_key)

    try:
        result = composio.tools.execute(
            "GMAIL_FETCH_EMAILS",
            user_id=COMPOSIO_USER_ID,
            arguments={"max_results": 3},
            # SDK requires a pinned toolkit version for manual execute(); "latest" is
            # rejected unless explicitly opted in. Phase 1 should pin an exact version
            # in tools/composio_bridge.py instead of skipping this check.
            dangerously_skip_version_check=True,
        )
    except Exception as exc:  # noqa: BLE001 - surface any API/auth error
        print(f"FAIL: GMAIL_FETCH_EMAILS raised: {exc}")
        print(
            f"Check that a GMAIL account is connected for user_id={COMPOSIO_USER_ID!r} "
            "(composio.connected_accounts.link) and that COMPOSIO_API_KEY is correct."
        )
        return 1

    print(f"Result: {result}")

    if isinstance(result, dict) and result.get("successful") is False:
        print(f"FAIL: GMAIL_FETCH_EMAILS reported failure: {result.get('error')}")
        return 1

    print("PASS: smoke_composio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
