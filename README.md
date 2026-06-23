# Email Agent 📧🤖

A personal **email agent** that operates on Gmail and Google Calendar, securely controlled through **Slack**.

This agent acts as an autonomous assistant capable of reading emails, drafting replies, and proposing calendar events. Crucially, **the agent cannot send emails or create calendar events without explicit human approval**. It surfaces proposed actions to you via interactive Slack messages, allowing you to approve, edit, or ignore them.

## 🌟 Key Features

1. **Summarize Email Threads**: Quickly catch up on long email chains directly from Slack.
2. **Calendar Event Extraction**: The agent reads emails, extracts event details, and proposes Google Calendar entries.
3. **Draft Replies**: It can generate contextual replies and save them directly as Gmail drafts.
4. **Approval-Gated Sending**: The agent surfaces its proposed replies in Slack via Block Kit. **It will never send an email without your explicit click of the "Approve" button.**
5. **Real-time Mail Triggers**: Reacts to new incoming mail automatically and orchestrates complex workflows (e.g., "summarize this thread, draft a reply, and propose the meeting it mentions").
6. **Prompt-Injection Defenses**: Employs structural separation of untrusted email content from agent instructions to ensure safety.

## 🏗️ Architecture & Stack

The agent is fundamentally an **orchestration system**, designed around a strict core/adapter split. The core intelligence is interface-agnostic, and the Slack app merely acts as a front door.

### Tech Stack
- **Reasoning Model**: NVIDIA NIM (Mistral Nemotron) for strong native function-calling.
- **Tool Access + Auth**: Composio (Managed OAuth, token refresh, hosted tools for Gmail/Google Calendar/Slack).
- **Interface**: Slack via Bolt SDK (Socket Mode).
- **Pending Action Store**: SQLite (Source of truth for actions awaiting approval).
- **Language**: Python

### The Safety Boundary
The Slack interface is how the human talks to the agent, but it is **NOT** a tool the LLM can call. The model never posts to Slack itself. An inbound email cannot inject a prompt that forces the agent to message you or take an unapproved action.

## 🚀 Setup Instructions

1. **Clone the repository and install dependencies:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -e ".[dev]"
   ```

2. **Configure your environment:**
   Copy `.env.example` to `.env` and fill in your real values. **Never commit your `.env` file.**
   - `NVIDIA_API_KEY`: Get this from [build.nvidia.com](https://build.nvidia.com) (NIM / Mistral Nemotron).
   - `COMPOSIO_API_KEY`: Get this from the [Composio dashboard](https://dashboard.composio.dev). Connect a `GMAIL` account for `user_id="default"` via `composio.connected_accounts.link(...)` before running the smoke tests.
   - `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_OWNER_USER_ID`: From your Slack app config (Socket Mode enabled, App-Level Token with `connections:write`, bot scope `chat:write`, subscribed to the `message.im` event).

3. **Run the Smoke Tests:**
   Ensure your dependencies are correctly configured by running the smoke scripts:
   ```powershell
   python scripts\smoke_nim.py
   python scripts\smoke_composio.py
   python scripts\smoke_slack.py
   ```
   Each script will print `PASS` or `FAIL` and explain what went wrong.

## 📚 Documentation
For deeper dives into the system design, safety rules, and phased build plan, check out:
- `CLAUDE.md`: The single source of truth for the project's architecture, memory, and rules.
- `BUILD_PLAN.md`: The phase-by-phase build plan used to construct the agent.
- `docs/`: Per-phase design notes and implementation details.
