"""Phase 0 smoke test: NVIDIA NIM (Mistral Nemotron).

Verifies:
1. A plain chat completion succeeds.
2. The model emits a well-formed tool call for one dummy tool.

Run:
    python scripts/smoke_nim.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import OpenAI

from config.settings import MissingEnvVar, load_settings

DUMMY_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a given city.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city to get the weather for.",
                },
            },
            "required": ["city"],
        },
    },
}


def main() -> int:
    try:
        settings = load_settings()
    except MissingEnvVar as exc:
        print(f"FAIL: {exc}")
        return 1

    client = OpenAI(api_key=settings.nvidia_api_key, base_url=settings.nvidia_base_url)

    # 1. Plain completion.
    try:
        completion = client.chat.completions.create(
            model=settings.nim_model,
            messages=[{"role": "user", "content": "Reply with exactly one word: pong"}],
            temperature=0.3,
            max_tokens=20,
        )
    except Exception as exc:  # noqa: BLE001 - surface any API error to the user
        print(f"FAIL: completion request raised: {exc}")
        return 1

    text = (completion.choices[0].message.content or "").strip()
    print(f"Completion response: {text!r}")
    if not text:
        print("FAIL: empty completion response")
        return 1

    # 2. Tool call with one dummy tool.
    try:
        tool_completion = client.chat.completions.create(
            model=settings.nim_model,
            messages=[{"role": "user", "content": "What is the weather in Tokyo right now?"}],
            tools=[DUMMY_TOOL],
            tool_choice="auto",
            temperature=0.3,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: tool-call request raised: {exc}")
        return 1

    message = tool_completion.choices[0].message
    tool_calls = message.tool_calls or []
    if not tool_calls:
        print(f"FAIL: model did not emit a tool call. Message content: {message.content!r}")
        return 1

    call = tool_calls[0]
    print(f"Tool call: {call.function.name}({call.function.arguments})")

    if call.function.name != "get_weather":
        print(f"FAIL: unexpected tool name {call.function.name!r}, expected 'get_weather'")
        return 1

    try:
        args = json.loads(call.function.arguments)
    except json.JSONDecodeError as exc:
        print(f"FAIL: tool call arguments are not valid JSON: {exc}")
        return 1

    if "city" not in args:
        print(f"FAIL: tool call missing required 'city' argument: {args}")
        return 1

    print("PASS: smoke_nim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
