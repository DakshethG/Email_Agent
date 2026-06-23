"""Minimal CLI adapter: type a command, print the agent's result.

For `create_event` pending actions, this is also the Phase 2 confirmation
surface: the parsed event is echoed back, and the real Google Calendar event
is only created after an explicit y/n confirm (CLAUDE.md §4.1).

Run with: python -m email_agent.interfaces.cli
"""

from __future__ import annotations

from typing import Any

from email_agent.core.agent import Agent
from email_agent.core.models import Command, PendingAction


def _format_event(payload: dict[str, Any]) -> str:
    lines = [
        f"  Title:     {payload.get('title') or '(none)'}",
        f"  Start:     {payload.get('start') or '(unknown)'}",
        f"  End:       {payload.get('end') or '(unknown)'}",
        f"  Timezone:  {payload.get('timezone') or '(unknown)'}",
    ]
    if payload.get("location"):
        lines.append(f"  Location:  {payload['location']}")
    if payload.get("attendees"):
        lines.append(f"  Attendees: {', '.join(payload['attendees'])}")
    if payload.get("description"):
        lines.append(f"  Notes:     {payload['description']}")
    return "\n".join(lines)


def _handle_create_event(agent: Agent, action: PendingAction) -> None:
    payload = action.payload
    print("\nProposed calendar event:")
    print(_format_event(payload))

    ambiguous = payload.get("ambiguous_fields") or []
    if ambiguous:
        print(f"\nCan't create this yet — unclear: {', '.join(ambiguous)}.")
        print("Please clarify and ask again.")
        return

    answer = input("\nCreate this event? (y/n) ").strip().lower()
    if answer not in {"y", "yes"}:
        print("Discarded.")
        return

    result = agent.create_event(payload)
    if result.get("successful"):
        print("Event created.")
    else:
        print(f"Failed to create event: {result.get('error', result)}")


def main() -> None:
    print("Email Agent CLI. Type a command (or 'exit' / Ctrl-D to quit).")
    agent = Agent()

    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            print()
            break

        if not line:
            continue
        if line.lower() in {"exit", "quit"}:
            break

        result = agent.handle(Command(text=line))
        print(result.text)

        for action in result.pending_actions:
            if action.type == "create_event":
                _handle_create_event(agent, action)
            else:
                print(f"\n[pending action] {action.type}: {action.payload}")


if __name__ == "__main__":
    main()
