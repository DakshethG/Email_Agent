# Phase 4 — Approval Gate + Send

## What was built

### `queue/store.py` + `queue/schema.sql`
SQLite-backed `ActionStore`: add / get / is_pending / mark_sent / mark_ignored /
update_payload. WAL mode. UUID primary keys. Source of truth — Slack is just
the surface.

### `interfaces/approval_handlers.py`
`SendApprovalFlow` class encapsulates the approve / ignore / edit-and-send
logic (owner check + idempotency + send_email call + status update). Extracted
from the Bolt adapter so it can be unit-tested without the framework.

### `core/agent.py` — additions
- `propose_reply` local tool (same intercept pattern as `propose_calendar_event`):
  model calls it → `handle()` catches it → `PendingAction(type="send_email")`. Never
  routed to Composio.
- `Agent.send_email(payload)` — the single send path. Calls Composio
  `SEND_EMAIL_SLUG` only when called explicitly by the approval handler.
- System prompt updated to describe capability 4 (propose for send) vs. capability
  3 (draft only).

### `interfaces/slack_app.py` — additions
Block Kit messages (Send / Edit / Ignore) for `send_email` PendingActions.
Button handlers: approve_send, edit_send, ignore_send. Modal handler:
edit_send_modal. All handlers ack() immediately then do slow work.

### `tools/gmail.py` — additions
`SEND_EMAIL_SLUG` constant (NOT in `ALLOWED_TOOL_SLUGS`) and
`build_send_email_arguments(payload)` mapper.

## How to run

### Verify the send tool slug first
```
python scripts/discover_send_tool.py
```
Update `SEND_EMAIL_SLUG` and `build_send_email_arguments()` in
`src/email_agent/tools/gmail.py` if the actual Composio slug differs.

### Run tests
```
python -m pytest
```
38 tests pass (9 queue, 10 approval flow, 8 agent core, 3 loop, 2 safety, 4 tools, 2 calendar).

### Run the Slack app
```
python -m email_agent.interfaces.slack_app
```
Then DM the bot:
- "reply to [email description]" → sends `propose_reply` → queued → Block Kit buttons appear
- Click ✅ Send → email sent, message updates to "✅ Sent."
- Click ✏️ Edit → modal opens prefilled → submit → edited version sent
- Click ✖️ Ignore → marked ignored, buttons replaced with "✖️ Ignored."

## What the tests cover
- Queue: add/get, is_pending, mark_sent/ignored, update_payload, idempotency,
  independence of multiple actions
- Approval flow: approve sends once, ignore sends nothing, edit sends modified
  text, non-owner rejected on all three actions, double-approve returns
  ALREADY_PROCESSED, approve-after-ignore returns ALREADY_PROCESSED
- Agent: propose_reply intercepted (no Composio call), send_email calls correct
  slug with mapped args, all prior Phase 1–3 tests still pass
- Gmail allow-list: send slug NOT in model registry

## Safety invariants enforced
- `SEND_EMAIL_SLUG` not in `ALLOWED_TOOL_SLUGS` → model can never call it (§4.1)
- `propose_reply` intercepted in `handle()` → `handle()` cannot trigger send (§4.1)
- Owner lock checked in every action handler before any store or send call (§4.3)
- `is_pending()` checked before every action → no double-send (§4.5)
