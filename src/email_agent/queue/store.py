"""SQLite-backed store for pending actions awaiting human approval.

Per CLAUDE.md §3: this is the source of truth for anything in the approval
queue. Slack messages are just the surface; the queue survives Slack
restarts and is the idempotency guard for Phase 4's send path.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = Path(__file__).parent / "schema.sql"


class ActionStore:
    """Thread-safe SQLite store (one connection per call; WAL mode)."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._init()

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA.read_text())

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ---------------------------------------------------------------- writes

    def add(self, action_type: str, payload: dict[str, Any]) -> str:
        """Insert a new pending action and return its action_id (UUID)."""
        action_id = str(uuid.uuid4())
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO pending_actions "
                "(action_id, type, payload, status, created_at, updated_at) "
                "VALUES (?, ?, ?, 'pending', ?, ?)",
                (action_id, action_type, json.dumps(payload), now, now),
            )
        return action_id

    def mark_sent(self, action_id: str) -> None:
        self._set_status(action_id, "sent")

    def mark_ignored(self, action_id: str) -> None:
        self._set_status(action_id, "ignored")

    def update_payload(self, action_id: str, payload: dict[str, Any]) -> None:
        """Replace the payload (e.g. after the user edits the draft body)."""
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                "UPDATE pending_actions SET payload = ?, updated_at = ? WHERE action_id = ?",
                (json.dumps(payload), now, action_id),
            )

    def _set_status(self, action_id: str, status: str) -> None:
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                "UPDATE pending_actions SET status = ?, updated_at = ? WHERE action_id = ?",
                (status, now, action_id),
            )

    # ----------------------------------------------------------------- reads

    def get(self, action_id: str) -> dict[str, Any] | None:
        """Return the row as a plain dict (payload deserialized), or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM pending_actions WHERE action_id = ?", (action_id,)
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["payload"] = json.loads(d["payload"])
        return d

    def is_pending(self, action_id: str) -> bool:
        """Return True iff the action exists and its status is 'pending'."""
        row = self.get(action_id)
        return row is not None and row["status"] == "pending"

    # ------------------------------------------------- message-ID idempotency

    def mark_message_processed(
        self, message_id: str, action_type: str, action_id: str
    ) -> None:
        """Record that `message_id` has been acted on (sent/confirmed).

        Subsequent calls to is_message_processed() for the same
        (message_id, action_type) pair will return True, preventing duplicate
        processing of the same email (Phase 5 / Phase 6 — CLAUDE.md §4.5).
        """
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_messages "
                "(message_id, action_type, action_id, processed_at) "
                "VALUES (?, ?, ?, ?)",
                (message_id, action_type, action_id, now),
            )

    def is_message_processed(self, message_id: str, action_type: str) -> bool:
        """Return True if this (message_id, action_type) pair has been acted on."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_messages "
                "WHERE message_id = ? AND action_type = ?",
                (message_id, action_type),
            ).fetchone()
        return row is not None


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
