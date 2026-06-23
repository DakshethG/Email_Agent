"""Tests for tools/calendar.py argument mapping."""

from __future__ import annotations

from email_agent.tools.calendar import build_create_event_arguments


def test_build_create_event_arguments_maps_all_fields() -> None:
    payload = {
        "title": "Team Sync",
        "start": "2026-06-20T15:00:00",
        "end": "2026-06-20T15:30:00",
        "timezone": "Asia/Kolkata",
        "location": "Room 4",
        "attendees": ["a@example.com", "b@example.com"],
        "description": "Quarterly planning",
        "ambiguous_fields": [],
    }

    arguments = build_create_event_arguments(payload)

    assert arguments == {
        "start_datetime": "2026-06-20T15:00:00",
        "end_datetime": "2026-06-20T15:30:00",
        "timezone": "Asia/Kolkata",
        "summary": "Team Sync",
        "location": "Room 4",
        "description": "Quarterly planning",
        "attendees": ["a@example.com", "b@example.com"],
    }


def test_build_create_event_arguments_omits_empty_optional_fields() -> None:
    payload = {
        "title": "",
        "start": "2026-06-20T15:00:00",
        "end": None,
        "timezone": "UTC",
        "location": None,
        "attendees": [],
        "description": None,
        "ambiguous_fields": [],
    }

    arguments = build_create_event_arguments(payload)

    assert arguments == {
        "start_datetime": "2026-06-20T15:00:00",
        "timezone": "UTC",
    }
