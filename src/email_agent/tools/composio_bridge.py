"""Maps a model tool call to a Composio tool execution.

Returns structured results (dicts) that get fed back into the NIM
tool-calling loop as tool messages.
"""

from __future__ import annotations

from typing import Any

from composio import Composio


class ComposioBridge:
    """Executes Composio tools on behalf of a single user."""

    def __init__(self, composio: Composio, user_id: str) -> None:
        self._composio = composio
        self._user_id = user_id

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute `tool_name` with `arguments` and return a structured result.

        Never raises — execution errors are returned as
        ``{"successful": False, "error": ...}`` so the model can see and
        react to them.
        """
        try:
            return dict(
                self._composio.tools.execute(
                    tool_name,
                    user_id=self._user_id,
                    arguments=arguments,
                    # Phase 1 uses "latest" tools; pin versions before Phase 4.
                    dangerously_skip_version_check=True,
                )
            )
        except Exception as exc:  # noqa: BLE001 - surface any error to the model
            return {"successful": False, "error": str(exc), "data": {}}
