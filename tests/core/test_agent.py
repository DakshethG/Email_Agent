"""Tests for Agent.handle(), Agent.create_event(), and Agent.send_email()."""

from __future__ import annotations

import json

from email_agent.core.agent import PROPOSE_EVENT_TOOL_NAME, PROPOSE_REPLY_TOOL_NAME, Agent
from email_agent.core.models import Command, PendingAction
from email_agent.tools.calendar import CREATE_EVENT_TOOL_SLUG
from email_agent.tools.gmail import SEND_EMAIL_SLUG
from tests.fakes import (
    FakeChoice,
    FakeCompletion,
    FakeFunctionCall,
    FakeMessage,
    FakeNimClient,
    FakeToolCall,
)


def test_handle_summarizes_thread_using_gmail_tool() -> None:
    tool_call = FakeToolCall(
        id="call_1",
        function=FakeFunctionCall(
            name="GMAIL_FETCH_MESSAGE_BY_THREAD_ID",
            arguments=json.dumps({"thread_id": "abc123"}),
        ),
    )
    client = FakeNimClient(
        [
            FakeCompletion(choices=[FakeChoice(message=FakeMessage(tool_calls=[tool_call]))]),
            FakeCompletion(
                choices=[
                    FakeChoice(
                        message=FakeMessage(
                            content=(
                                "- Alice asked about the Q3 budget.\n"
                                "- Bob agreed to send numbers Friday."
                            )
                        )
                    )
                ]
            ),
        ]
    )

    calls: list[tuple[str, dict]] = []

    def tool_executor(name: str, arguments: dict) -> dict:
        calls.append((name, arguments))
        return {
            "successful": True,
            "data": {
                "messages": [
                    {"from": "alice@example.com", "snippet": "What's our Q3 budget?"},
                    {"from": "bob@example.com", "snippet": "I'll send the numbers Friday."},
                ]
            },
        }

    agent = Agent(
        nim_client=client,
        tools=[{"type": "function", "function": {"name": "GMAIL_FETCH_MESSAGE_BY_THREAD_ID"}}],
        tool_executor=tool_executor,
        default_timezone="UTC",
    )

    result = agent.handle(Command(text="summarize thread abc123"))

    assert "Alice" in result.text
    assert "Bob" in result.text
    assert result.pending_actions == []
    assert calls == [("GMAIL_FETCH_MESSAGE_BY_THREAD_ID", {"thread_id": "abc123"})]


def test_handle_returns_text_without_tool_calls() -> None:
    client = FakeNimClient([FakeCompletion(choices=[FakeChoice(message=FakeMessage(content="Hi there!"))])])

    agent = Agent(nim_client=client, tools=[], tool_executor=lambda *_: {}, default_timezone="UTC")

    result = agent.handle(Command(text="hello"))

    assert result.text == "Hi there!"
    assert result.pending_actions == []


def test_handle_proposes_event_with_explicit_timezone() -> None:
    proposal_args = {
        "title": "Project Kickoff",
        "start": "2026-06-22T10:00:00",
        "end": "2026-06-22T11:00:00",
        "timezone": "America/New_York",
        "location": "Conference Room A",
        "attendees": ["alice@example.com"],
        "description": "Kickoff meeting",
        "ambiguous_fields": [],
    }
    tool_call = FakeToolCall(
        id="call_propose",
        function=FakeFunctionCall(name=PROPOSE_EVENT_TOOL_NAME, arguments=json.dumps(proposal_args)),
    )
    client = FakeNimClient(
        [
            FakeCompletion(choices=[FakeChoice(message=FakeMessage(tool_calls=[tool_call]))]),
            FakeCompletion(
                choices=[
                    FakeChoice(
                        message=FakeMessage(
                            content=(
                                "Found it: 'Project Kickoff' on 2026-06-22 10:00-11:00 "
                                "(America/New_York) at Conference Room A with alice@example.com."
                            )
                        )
                    )
                ]
            ),
        ]
    )

    calls: list[tuple[str, dict]] = []

    def tool_executor(name: str, arguments: dict) -> dict:
        calls.append((name, arguments))
        return {"successful": True, "data": {"messages": []}}

    agent = Agent(
        nim_client=client,
        tools=[{"type": "function", "function": {"name": "GMAIL_FETCH_EMAILS"}}],
        tool_executor=tool_executor,
        default_timezone="Asia/Kolkata",
    )

    result = agent.handle(Command(text="propose a calendar event for the kickoff email"))

    assert result.pending_actions == [PendingAction(type="create_event", payload=proposal_args)]
    assert "America/New_York" in result.text
    assert "10:00" in result.text
    # the local propose tool is intercepted before it ever reaches the bridge
    assert calls == []


def test_handle_flags_ambiguous_date_without_guessing() -> None:
    proposal_args = {
        "title": "Catch-up call",
        "start": None,
        "end": None,
        "timezone": "Asia/Kolkata",
        "location": None,
        "attendees": [],
        "description": None,
        "ambiguous_fields": ["start", "end"],
    }
    tool_call = FakeToolCall(
        id="call_propose",
        function=FakeFunctionCall(name=PROPOSE_EVENT_TOOL_NAME, arguments=json.dumps(proposal_args)),
    )
    client = FakeNimClient(
        [
            FakeCompletion(choices=[FakeChoice(message=FakeMessage(tool_calls=[tool_call]))]),
            FakeCompletion(
                choices=[
                    FakeChoice(
                        message=FakeMessage(
                            content=(
                                "The email doesn't say when this is happening, so I "
                                "couldn't determine the start/end time. Can you clarify?"
                            )
                        )
                    )
                ]
            ),
        ]
    )

    calls: list[tuple[str, dict]] = []

    def tool_executor(name: str, arguments: dict) -> dict:
        calls.append((name, arguments))
        return {"successful": True, "data": {}}

    agent = Agent(
        nim_client=client,
        tools=[],
        tool_executor=tool_executor,
        default_timezone="Asia/Kolkata",
    )

    result = agent.handle(Command(text="propose an event for the catch-up email"))

    assert len(result.pending_actions) == 1
    payload = result.pending_actions[0].payload
    assert payload["ambiguous_fields"] == ["start", "end"]
    assert payload["start"] is None
    assert payload["end"] is None
    # nothing is executed -- especially not a create call -- when ambiguous
    assert calls == []


def test_handle_creates_gmail_draft_linked_to_thread() -> None:
    draft_args = {
        "thread_id": "abc123",
        "recipient_email": "alice@example.com",
        "body": "Thanks for the update -- I'll send the numbers Friday.",
    }
    tool_call = FakeToolCall(
        id="call_draft",
        function=FakeFunctionCall(name="GMAIL_CREATE_EMAIL_DRAFT", arguments=json.dumps(draft_args)),
    )
    client = FakeNimClient(
        [
            FakeCompletion(choices=[FakeChoice(message=FakeMessage(tool_calls=[tool_call]))]),
            FakeCompletion(
                choices=[
                    FakeChoice(
                        message=FakeMessage(
                            content=(
                                "I've drafted a reply to alice@example.com in that thread: "
                                "\"Thanks for the update -- I'll send the numbers Friday.\""
                            )
                        )
                    )
                ]
            ),
        ]
    )

    calls: list[tuple[str, dict]] = []

    def tool_executor(name: str, arguments: dict) -> dict:
        calls.append((name, arguments))
        return {"successful": True, "data": {"id": "draft_1", "message": {"threadId": "abc123"}}}

    agent = Agent(
        nim_client=client,
        tools=[{"type": "function", "function": {"name": "GMAIL_CREATE_EMAIL_DRAFT"}}],
        tool_executor=tool_executor,
        default_timezone="UTC",
    )

    result = agent.handle(Command(text="draft a reply to alice's email"))

    # the draft tool is executed for real -- drafting is inherently safe
    assert calls == [("GMAIL_CREATE_EMAIL_DRAFT", draft_args)]
    assert "alice@example.com" in result.text
    assert result.pending_actions == []


def test_handle_proposes_reply_for_send_approval() -> None:
    proposal_args = {
        "thread_id": "abc123",
        "recipient_email": "alice@example.com",
        "body": "Thanks for reaching out — I'll follow up by Friday.",
    }
    tool_call = FakeToolCall(
        id="call_propose_reply",
        function=FakeFunctionCall(
            name=PROPOSE_REPLY_TOOL_NAME, arguments=json.dumps(proposal_args)
        ),
    )
    client = FakeNimClient(
        [
            FakeCompletion(choices=[FakeChoice(message=FakeMessage(tool_calls=[tool_call]))]),
            FakeCompletion(
                choices=[
                    FakeChoice(
                        message=FakeMessage(
                            content="Your reply is queued for approval."
                        )
                    )
                ]
            ),
        ]
    )

    calls: list[tuple[str, dict]] = []

    def tool_executor(name: str, arguments: dict) -> dict:
        calls.append((name, arguments))
        return {"successful": True}

    agent = Agent(
        nim_client=client,
        tools=[],
        tool_executor=tool_executor,
        default_timezone="UTC",
    )

    result = agent.handle(Command(text="reply to alice's latest email"))

    # propose_reply is intercepted locally — never forwarded to Composio
    assert calls == []
    assert result.pending_actions == [
        PendingAction(type="send_email", payload=proposal_args)
    ]
    assert "approval" in result.text.lower()


def test_send_email_executes_send_tool_with_mapped_arguments() -> None:
    calls: list[tuple[str, dict]] = []

    def tool_executor(name: str, arguments: dict) -> dict:
        calls.append((name, arguments))
        return {"successful": True, "data": {"message_id": "msg_sent_1"}}

    agent = Agent(
        nim_client=FakeNimClient([]),
        tools=[],
        tool_executor=tool_executor,
        default_timezone="UTC",
    )

    payload = {
        "thread_id": "abc123",
        "recipient_email": "alice@example.com",
        "body": "Approved reply text.",
    }

    result = agent.send_email(payload)

    assert result["successful"] is True
    assert calls == [
        (
            SEND_EMAIL_SLUG,
            {
                "recipient_email": "alice@example.com",
                "body": "Approved reply text.",
                "thread_id": "abc123",
            },
        )
    ]


def test_use_fast_model_routes_to_fast_nim_client() -> None:
    """use_fast_model=True uses the injected fast_nim_client, not the primary one."""
    primary_client = FakeNimClient([])
    fast_client = FakeNimClient(
        [FakeCompletion(choices=[FakeChoice(message=FakeMessage(content="Fast summary."))])]
    )

    agent = Agent(
        nim_client=primary_client,
        fast_nim_client=fast_client,
        tools=[],
        tool_executor=lambda *_: {},
        default_timezone="UTC",
    )

    result = agent.handle(Command(text="summarize my inbox"), use_fast_model=True)

    assert result.text == "Fast summary."
    assert len(primary_client.calls) == 0, "Primary client must not be called when use_fast_model=True"
    assert len(fast_client.calls) == 1


def test_use_fast_model_false_uses_primary_nim_client() -> None:
    """use_fast_model=False (default) uses the primary client."""
    fast_client = FakeNimClient([])
    primary_client = FakeNimClient(
        [FakeCompletion(choices=[FakeChoice(message=FakeMessage(content="Primary response."))])]
    )

    agent = Agent(
        nim_client=primary_client,
        fast_nim_client=fast_client,
        tools=[],
        tool_executor=lambda *_: {},
        default_timezone="UTC",
    )

    result = agent.handle(Command(text="do something"))

    assert result.text == "Primary response."
    assert len(fast_client.calls) == 0
    assert len(primary_client.calls) == 1


def test_create_event_executes_calendar_tool_with_mapped_arguments() -> None:
    calls: list[tuple[str, dict]] = []

    def tool_executor(name: str, arguments: dict) -> dict:
        calls.append((name, arguments))
        return {
            "successful": True,
            "data": {"response_data": {"id": "evt_1", "htmlLink": "https://calendar.google.com/event?eid=evt_1"}},
        }

    agent = Agent(
        nim_client=FakeNimClient([]),
        tools=[],
        tool_executor=tool_executor,
        default_timezone="Asia/Kolkata",
    )

    payload = {
        "title": "Team Sync",
        "start": "2026-06-22T10:00:00",
        "end": "2026-06-22T11:00:00",
        "timezone": "America/New_York",
        "location": "Conference Room A",
        "attendees": ["alice@example.com"],
        "description": "Kickoff meeting",
        "ambiguous_fields": [],
    }

    result = agent.create_event(payload)

    assert result["successful"] is True
    assert calls == [
        (
            CREATE_EVENT_TOOL_SLUG,
            {
                "start_datetime": "2026-06-22T10:00:00",
                "end_datetime": "2026-06-22T11:00:00",
                "timezone": "America/New_York",
                "summary": "Team Sync",
                "location": "Conference Room A",
                "description": "Kickoff meeting",
                "attendees": ["alice@example.com"],
            },
        )
    ]
