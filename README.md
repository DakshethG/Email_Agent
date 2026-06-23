# Email Agent

Personal email agent on Gmail + Google Calendar, controlled through Slack. See
`CLAUDE.md` for architecture and safety rules, `BUILD_PLAN.md` for the phased
build plan, and `docs/` for per-phase design notes.

## Setup

1. Create a virtual environment and install dependencies:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -e ".[dev]"
   ```

2. Copy `.env.example` to `.env` and fill in real values. **Never commit `.env`.**

   - `NVIDIA_API_KEY` — from [build.nvidia.com](https://build.nvidia.com) (NIM /
     Mistral Nemotron).
   - `COMPOSIO_API_KEY` — from the [Composio dashboard](https://dashboard.composio.dev).
     Connect a `GMAIL` account for `user_id="default"` via
     `composio.connected_accounts.link(...)` before running `smoke_composio.py`.
   - `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_OWNER_USER_ID` — from your Slack
     app config (Socket Mode enabled, App-Level Token with `connections:write`,
     bot scope `chat:write`, subscribed to the `message.im` event).

3. Run the Phase 0 smoke tests (see `docs/phase0.md` for details):

   ```powershell
   python scripts\smoke_nim.py
   python scripts\smoke_composio.py
   python scripts\smoke_slack.py
   ```

Each script prints `PASS` or `FAIL` and explains what went wrong.
