"""The NIM tool-calling loop.

Sends `messages` + `tools` to the model, executes any requested tool calls via
`tool_executor`, feeds the results back as tool messages, and repeats until the
model returns a final text answer (no more tool calls).
"""

from __future__ import annotations

import json
from typing import Any, Callable, Protocol

ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]


class ChatClient(Protocol):
    """Anything with NimClient's `chat` signature."""

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
    ) -> Any: ...


def run_loop(
    client: ChatClient,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_executor: ToolExecutor,
    max_iterations: int = 8,
) -> str:
    """Run the tool-calling loop and return the model's final text reply.

    `messages` is mutated in place with the assistant/tool turns produced
    along the way, so callers can inspect the full transcript afterwards.
    """
    for _ in range(max_iterations):
        completion = client.chat(messages, tools=tools)
        message = completion.choices[0].message

        if not message.tool_calls:
            return message.content or ""

        messages.append(message.model_dump(exclude_none=True))

        for tool_call in message.tool_calls:
            arguments = json.loads(tool_call.function.arguments or "{}")
            result = tool_executor(tool_call.function.name, arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )

    raise RuntimeError(f"Tool-calling loop did not converge after {max_iterations} iterations")
