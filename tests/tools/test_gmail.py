"""Tests for the Gmail tool allow-list (CLAUDE.md §4.4)."""

from __future__ import annotations

from email_agent.tools.gmail import DRAFT_GMAIL_TOOLS, READ_ONLY_GMAIL_TOOLS, SEND_EMAIL_SLUG
from email_agent.tools.registry import ALLOWED_TOOL_SLUGS


def test_draft_tool_is_registered() -> None:
    assert "GMAIL_CREATE_EMAIL_DRAFT" in ALLOWED_TOOL_SLUGS


def test_registry_has_no_send_forward_or_delete_tools() -> None:
    forbidden_markers = ("SEND", "FORWARD", "DELETE")
    for slug in ALLOWED_TOOL_SLUGS:
        for marker in forbidden_markers:
            assert marker not in slug, f"{slug} contains forbidden marker {marker}"


def test_allowed_slugs_match_gmail_allow_lists() -> None:
    assert ALLOWED_TOOL_SLUGS == [*READ_ONLY_GMAIL_TOOLS, *DRAFT_GMAIL_TOOLS]


def test_send_slug_is_not_in_model_registry() -> None:
    # The send tool must never appear in the model's tool list (CLAUDE.md §4.1).
    assert SEND_EMAIL_SLUG not in ALLOWED_TOOL_SLUGS
