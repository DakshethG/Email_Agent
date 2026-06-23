"""Tests for NimClient rate-limit retry and model-override behaviour."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from email_agent.llm.nim_client import NimClient, _MAX_RETRIES


def _fake_settings(model: str = "primary-model", fallback: str = "cheap-model") -> MagicMock:
    s = MagicMock()
    s.nvidia_api_key = "test-key"
    s.nvidia_base_url = "https://fake.api.test"
    s.nim_model = model
    s.nim_fallback_model = fallback
    return s


class _FakeRateLimitError(Exception):
    """Substituted for openai.RateLimitError in tests via monkeypatch."""


class _FakeCompletion:
    def __init__(self, content: str = "ok") -> None:
        self.choices = [MagicMock(message=MagicMock(content=content, tool_calls=None))]


def test_rate_limit_retries_then_succeeds(monkeypatch) -> None:
    """Client retries on RateLimitError and returns the successful completion."""
    monkeypatch.setattr("email_agent.llm.nim_client.RateLimitError", _FakeRateLimitError)

    call_count = 0
    success = _FakeCompletion("hello")

    def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise _FakeRateLimitError("rate limited")
        return success

    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))

    with patch("email_agent.llm.nim_client.OpenAI") as mock_cls:
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.side_effect = mock_create
        mock_cls.return_value = mock_openai

        nim = NimClient(_fake_settings())
        result = nim.chat([{"role": "user", "content": "test"}])

    assert result is success
    assert call_count == 3
    assert sleeps == [1, 2]  # exponential: BASE * 2^0 = 1s, BASE * 2^1 = 2s


def test_rate_limit_reraises_after_max_retries(monkeypatch) -> None:
    """After _MAX_RETRIES exhausted, RateLimitError propagates to the caller."""
    monkeypatch.setattr("email_agent.llm.nim_client.RateLimitError", _FakeRateLimitError)

    def always_fail(**kwargs):
        raise _FakeRateLimitError("always fails")

    monkeypatch.setattr("time.sleep", lambda _: None)

    with patch("email_agent.llm.nim_client.OpenAI") as mock_cls:
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.side_effect = always_fail
        mock_cls.return_value = mock_openai

        nim = NimClient(_fake_settings())
        with pytest.raises(_FakeRateLimitError):
            nim.chat([{"role": "user", "content": "test"}])


def test_max_retries_attempts_correct_count(monkeypatch) -> None:
    """Exactly _MAX_RETRIES attempts are made before giving up."""
    monkeypatch.setattr("email_agent.llm.nim_client.RateLimitError", _FakeRateLimitError)
    monkeypatch.setattr("time.sleep", lambda _: None)

    call_count = 0

    def count_calls(**kwargs):
        nonlocal call_count
        call_count += 1
        raise _FakeRateLimitError("rate limited")

    with patch("email_agent.llm.nim_client.OpenAI") as mock_cls:
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.side_effect = count_calls
        mock_cls.return_value = mock_openai

        nim = NimClient(_fake_settings())
        with pytest.raises(_FakeRateLimitError):
            nim.chat([{"role": "user", "content": "test"}])

    assert call_count == _MAX_RETRIES


def test_fast_chat_uses_fallback_model(monkeypatch) -> None:
    """fast_chat() passes the configured fallback model, not the primary."""
    used_models: list[str] = []

    def capture_model(**kwargs):
        used_models.append(kwargs.get("model", ""))
        return _FakeCompletion()

    with patch("email_agent.llm.nim_client.OpenAI") as mock_cls:
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.side_effect = capture_model
        mock_cls.return_value = mock_openai

        nim = NimClient(_fake_settings(model="primary-model", fallback="cheap-model"))
        nim.fast_chat([{"role": "user", "content": "summarize"}])

    assert used_models == ["cheap-model"]


def test_chat_model_override_takes_precedence(monkeypatch) -> None:
    """An explicit model= kwarg overrides the instance default."""
    used_models: list[str] = []

    def capture_model(**kwargs):
        used_models.append(kwargs.get("model", ""))
        return _FakeCompletion()

    with patch("email_agent.llm.nim_client.OpenAI") as mock_cls:
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.side_effect = capture_model
        mock_cls.return_value = mock_openai

        nim = NimClient(_fake_settings(model="primary-model"))
        nim.chat([{"role": "user", "content": "test"}], model="override-model")

    assert used_models == ["override-model"]
