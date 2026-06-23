"""Thin wrapper around the NVIDIA NIM OpenAI-compatible chat completions API."""

from __future__ import annotations

import time
from typing import Any

from openai import OpenAI, RateLimitError

from config.settings import Settings

TEMPERATURE = 0.3
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 1


class NimClient:
    """Wraps the OpenAI SDK pointed at the NIM base URL."""

    def __init__(self, settings: Settings, model: str | None = None) -> None:
        self._client = OpenAI(api_key=settings.nvidia_api_key, base_url=settings.nvidia_base_url)
        self._model = model or settings.nim_model
        self._fallback_model = settings.nim_fallback_model

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        model: str | None = None,
    ):
        """Send a chat completion request, retrying with exponential backoff on 429."""
        resolved_model = model or self._model
        kwargs: dict[str, Any] = {}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        for attempt in range(_MAX_RETRIES):
            try:
                return self._client.chat.completions.create(
                    model=resolved_model,
                    messages=messages,
                    temperature=TEMPERATURE,
                    **kwargs,
                )
            except RateLimitError:
                if attempt == _MAX_RETRIES - 1:
                    raise
                time.sleep(_BASE_BACKOFF_SECONDS * (2 ** attempt))

    def fast_chat(self, messages: list[dict[str, Any]]):
        """Use the cheaper fallback model for text-only tasks (no tool calls)."""
        return self.chat(messages, model=self._fallback_model)
