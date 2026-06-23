"""Lightweight stand-ins for the NIM/OpenAI chat completion objects.

These mimic just enough of the OpenAI SDK's response shape (`.choices[0]
.message`, `.tool_calls`, `.model_dump()`) for `core.loop.run_loop` to work
against them, without making any real API calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FakeFunctionCall:
    name: str
    arguments: str


@dataclass
class FakeToolCall:
    id: str
    function: FakeFunctionCall
    type: str = "function"


@dataclass
class FakeMessage:
    content: str | None = None
    tool_calls: list[FakeToolCall] | None = None
    role: str = "assistant"

    def model_dump(self, exclude_none: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls is not None:
            data["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in self.tool_calls
            ]
        if exclude_none:
            data = {k: v for k, v in data.items() if v is not None}
        return data


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeCompletion:
    choices: list[FakeChoice]


class FakeNimClient:
    """Returns pre-scripted completions in order; records every call."""

    def __init__(self, completions: list[FakeCompletion]) -> None:
        self._completions = list(completions)
        self.calls: list[dict[str, Any]] = []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        model: str | None = None,
    ) -> FakeCompletion:
        self.calls.append(
            {
                "messages": [dict(m) for m in messages],
                "tools": tools,
                "tool_choice": tool_choice,
            }
        )
        return self._completions.pop(0)
