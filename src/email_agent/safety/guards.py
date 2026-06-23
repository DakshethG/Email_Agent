"""Safety guards applied at the interface and configuration layers.

Per CLAUDE.md §4.3: Slack interactions are only honored from the configured
owner user ID. Per §4.4: the model's tool allow-list must never include
destructive (bulk/permanent-delete or irreversible) actions.
"""

from __future__ import annotations

# Substrings that flag a Composio tool slug as destructive / irreversible.
_DESTRUCTIVE_MARKERS = ("DELETE", "TRASH", "PURGE", "BATCH_DELETE", "PERMANENT")


def is_owner(user_id: str, owner_user_id: str) -> bool:
    """Return True if `user_id` is the configured Slack owner."""
    return user_id == owner_user_id


def validate_no_destructive_tools(tool_slugs: list[str]) -> None:
    """Raise ValueError if any slug matches a destructive action marker.

    Call this at startup (e.g. inside build_tool_schemas) to catch accidental
    inclusion of bulk-delete or irreversible Composio actions in the model's
    allow-list (CLAUDE.md §4.4).
    """
    for slug in tool_slugs:
        upper = slug.upper()
        for marker in _DESTRUCTIVE_MARKERS:
            if marker in upper:
                raise ValueError(
                    f"Destructive tool '{slug}' must not be in the model's allow-list. "
                    "Remove it from ALLOWED_TOOL_SLUGS (CLAUDE.md §4.4)."
                )
