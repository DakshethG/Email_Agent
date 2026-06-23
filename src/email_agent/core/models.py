"""Core dataclasses shared between the agent core and all interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Command:
    """A request from an interface (CLI, Slack) to the agent core."""

    text: str


@dataclass
class PendingAction:
    """An action the agent has proposed but not executed.

    Interfaces surface these for human approval; the agent core never
    executes them itself.
    """

    type: str
    payload: dict[str, Any]


@dataclass
class AgentResult:
    """The result of agent.handle(command)."""

    text: str
    pending_actions: list[PendingAction] = field(default_factory=list)
