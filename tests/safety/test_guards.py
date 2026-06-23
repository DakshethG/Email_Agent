"""Tests for safety guards: owner lock (§4.3) and destructive tool check (§4.4)."""

from __future__ import annotations

import pytest

from email_agent.safety.guards import is_owner, validate_no_destructive_tools


def test_is_owner_matches_configured_user() -> None:
    assert is_owner("U0BAMN1SS8Z", "U0BAMN1SS8Z") is True


def test_is_owner_rejects_other_users() -> None:
    assert is_owner("U999OTHER", "U0BAMN1SS8Z") is False


def test_validate_allows_safe_slugs() -> None:
    validate_no_destructive_tools(["GMAIL_FETCH_EMAILS", "GMAIL_CREATE_EMAIL_DRAFT"])


def test_validate_rejects_delete_slug() -> None:
    with pytest.raises(ValueError, match="Destructive tool"):
        validate_no_destructive_tools(["GMAIL_DELETE_MESSAGE"])


def test_validate_rejects_trash_slug() -> None:
    with pytest.raises(ValueError, match="Destructive tool"):
        validate_no_destructive_tools(["GMAIL_TRASH_EMAIL"])


def test_validate_rejects_purge_slug() -> None:
    with pytest.raises(ValueError, match="Destructive tool"):
        validate_no_destructive_tools(["GMAIL_PURGE_INBOX"])


def test_validate_rejects_batch_delete() -> None:
    with pytest.raises(ValueError, match="Destructive tool"):
        validate_no_destructive_tools(["GMAIL_BATCH_DELETE_EMAILS"])
