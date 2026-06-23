# Phase 6 — Real-time Triggers + Composition

## What was built

### `llm/nim_client.py` — retry + model routing
- `NimClient.__init__` accepts optional `model` override (for fast-client construction).
- `chat()` accepts a per-call `model=` kwarg.
- `fast_chat(messages)` calls `chat()` with `settings.nim_fallback_model` (Llama 3.3 70B).
- Retry on `openai.RateLimitError`: up to 3 attempts with exponential backoff (1 s, 2 s).
  Raises after the third failure so callers see the error.

### `core/agent.py` — fast-model routing + composed workflow prompt
- `Agent.__init__` gains `fast_nim_client` injectable param.
  Production: second `NimClient` pointing at the fallback model.
  Tests: reuses the injected `nim_client` so no env vars are needed.
- `handle()` gains `use_fast_model: bool = False`.
  When True, `run_loop` uses the fast client — no tool calls beyond what the
  fast model supports (adequate for summarisation-only, skips the full NIM quota).
- System prompt updated with a "For composed requests" section: read the email once,
  then call `propose_calendar_event` and/or `propose_reply` in the same loop.

### `interfaces/blocks.py` — shared Block Kit builders (new)
- `send_email_blocks()` and `create_event_blocks()` extracted from `slack_app.py`.
- `EMAIL_TERMINAL` and `CALENDAR_TERMINAL` status dicts also moved here.
- `slack_app.py` re-exports `_`-prefixed aliases for backward compatibility.
- `triggers/gmail_watch.py` imports from `interfaces/blocks.py` to avoid a circular import.

### `interfaces/slack_app.py` — fast-model routing + watcher startup
- `_wants_fast_model(text)` heuristic: True for "summarize / summary / tldr" commands
  that mention no action word ("reply / send / event / meeting / draft").
- DM handler passes `use_fast_model=_wants_fast_model(text)` to `agent.handle()`.
- `main()` starts `GmailWatcher.start_background()` in a daemon thread before Bolt starts.
  If the watcher fails to initialize (missing dep, API error), it logs and continues —
  the Slack bot still runs.

### `triggers/gmail_watch.py` — new file
- `GmailWatcher` class with injectable `_composio` and `_slack_client` for tests.
- `start()` — blocking Composio trigger listener.
- `start_background()` — daemon thread wrapper.
- `_process_event(payload)` — the core business logic:
  1. Extract `threadId` / `messageId` from the Composio payload.
  2. Idempotency: skip if `is_message_processed(message_id, "auto_trigger")`.
  3. Call `agent.handle()` with a composed command.
  4. Post summary text to owner Slack DM.
  5. Post each `PendingAction` via existing Block Kit approval blocks.
  6. `mark_message_processed(message_id, "auto_trigger", "auto_trigger")`.
- No new send path — all replies still go through `SendApprovalFlow` / Slack buttons.

### `scripts/setup_gmail_trigger.py`
Enables `GMAIL_NEW_EMAIL_TRIGGER` on Composio for the configured user. Run once before
starting the app.

### `scripts/discover_trigger.py`
Lists available Gmail trigger slugs from the Composio API. Use this if the trigger
name changes between SDK versions.

## How to run

```
# 1. Enable the Gmail trigger (one-time setup)
python scripts/setup_gmail_trigger.py

# 2. Run all tests
python -m pytest

# 3. Start the app (watcher starts automatically in a background thread)
python -m email_agent.interfaces.slack_app
```

## Test coverage (14 new tests)

**`tests/llm/test_nim_client.py`** (5 tests):
- 429 retries twice then returns successful completion; sleep durations are 1 s and 2 s.
- 429 reraises after `_MAX_RETRIES` exhausted.
- Exactly `_MAX_RETRIES` attempts made before giving up.
- `fast_chat()` uses the fallback model.
- Per-call `model=` override takes precedence over instance default.

**`tests/triggers/test_gmail_watch.py`** (7 tests):
- New email event calls agent and posts summary.
- Duplicate message_id skips agent entirely.
- Missing threadId skips agent.
- Proposed reply is stored and posted with Block Kit.
- Proposed event is stored and posted with Block Kit.
- Duplicate reply (already-sent source_message_id) skips the block post.
- Composed result with both reply + event posts two approval blocks.

**`tests/core/test_agent.py`** (2 new tests):
- `use_fast_model=True` routes to `fast_nim_client`, not primary.
- `use_fast_model=False` (default) routes to primary client.

**Total: 78 tests, all passing.**

## Safety invariants — unchanged

All Phase 4/5 safety invariants remain in force:
- No new send path — trigger replies go through `SendApprovalFlow`.
- Prompt injection defence preamble in every system prompt.
- `SEND_EMAIL_SLUG` absent from `ALLOWED_TOOL_SLUGS`.
- `validate_no_destructive_tools` runs at import time.
- `processed_messages` dedup covers both manual Slack commands and trigger events.
