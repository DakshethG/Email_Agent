"""Central configuration: loads and validates environment variables.

Fails loudly if a required secret is missing. Never hardcode secrets here —
copy .env.example to .env and fill in real values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class MissingEnvVar(RuntimeError):
    """Raised when a required environment variable is not set."""


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingEnvVar(
            f"Missing required environment variable: {name}. "
            "Copy .env.example to .env and fill in real values."
        )
    return value


@dataclass(frozen=True)
class Settings:
    nvidia_api_key: str
    nvidia_base_url: str
    nim_model: str
    nim_fallback_model: str

    composio_api_key: str
    composio_user_id: str

    slack_bot_token: str
    slack_app_token: str
    slack_owner_user_id: str

    pending_db_path: Path
    default_timezone: str


def load_settings() -> Settings:
    """Load and validate settings from the environment (.env)."""
    return Settings(
        nvidia_api_key=_require("NVIDIA_API_KEY"),
        nvidia_base_url=os.environ.get(
            "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
        ),
        nim_model=os.environ.get("NIM_MODEL", "mistralai/mistral-nemotron"),
        nim_fallback_model=os.environ.get(
            "NIM_FALLBACK_MODEL", "meta/llama-3.3-70b-instruct"
        ),
        composio_api_key=_require("COMPOSIO_API_KEY"),
        composio_user_id=os.environ.get("COMPOSIO_USER_ID", "default"),
        slack_bot_token=_require("SLACK_BOT_TOKEN"),
        slack_app_token=_require("SLACK_APP_TOKEN"),
        slack_owner_user_id=_require("SLACK_OWNER_USER_ID"),
        pending_db_path=Path(os.environ.get("PENDING_DB_PATH", "./pending.db")),
        default_timezone=os.environ.get("DEFAULT_TIMEZONE", "Asia/Kolkata"),
    )
