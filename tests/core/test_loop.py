"""Tests for the NIM tool-calling loop."""

from __future__ import annotations

import json

import pytest

from email_agent.core.loop import run_loop
from tests.fakes import (
    FakeChoice,
    FakeCompletion,
    FakeFunctionCall,
    FakeMessage,
    FakeNimClient,
    FakeToolCall,
)


def test_run_loop_calls_tool_then_returns_final_text() -> None:
    tool_call = FakeToolCall(
        id="call_1",
        function=FakeFunctionCall(
            name="GMAIL_FETCH_EMAILS", arguments=json.dumps({"query": "is:unread"})
        ),
    )
    client = FakeNimClient(
        [
            FakeCompletion(choices=[FakeChoice(message=FakeMessage(tool_calls=[tool_call]))]),
            FakeCompletion(
                choices=[FakeChoice(message=FakeMessage(content="Summary: nothing urgent."))]
            ),
        ]
    )

    calls: list[tuple[str, dict]] = []

    def tool_executor(name: str, arguments: dict) -> dict:
        calls.append((name, arguments))
        return {"successful": True, "data": {"messages": [{"subject": "Hi"}]}}

    messages = [{"role": "user", "content": "summarize my inbox"}]
    tools = [{"type": "function", "function": {"name": "GMAIL_FETCH_EMAILS"}}]

    result = run_loop(client, messages, tools, tool_executor)

    assert result == "Summary: nothing urgent."
    assert calls == [("GMAIL_FETCH_EMAILS", {"query": "is:unread"})]
    assert len(client.calls) == 2

    tool_messages = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "call_1"
    assert json.loads(tool_messages[0]["content"])["successful"] is True


def test_run_loop_returns_text_immediately_when_no_tool_call() -> None:
    client = FakeNimClient([FakeCompletion(choices=[FakeChoice(message=FakeMessage(content="Hello!"))])])

    def tool_executor(name: str, arguments: dict) -> dict:
        raise AssertionError("tool_executor should not be called")

    result = run_loop(client, [{"role": "user", "content": "hi"}], [], tool_executor)

    assert result == "Hello!"
    assert len(client.calls) == 1


def test_run_loop_raises_if_it_never_converges() -> None:
    tool_call = FakeToolCall(id="call_1", function=FakeFunctionCall(name="NOOP", arguments="{}"))
    completion = FakeCompletion(choices=[FakeChoice(message=FakeMessage(tool_calls=[tool_call]))])

    class InfiniteClient(FakeNimClient):
        def chat(self, messages, tools=None, tool_choice="auto"):
            self.calls.append({})
            return completion

    client = InfiniteClient([])

    with pytest.raises(RuntimeError):
        run_loop(
            client,
            [{"role": "user", "content": "x"}],
            [],
            tool_executor=lambda *_: {},
            max_iterations=2,
        )
