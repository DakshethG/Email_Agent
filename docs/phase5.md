# Phase 5 — Reply-in-thread + Hardening

## What was built

### `safety/injection.py`
- `INJECTION_DEFENSE_PREAMBLE` — system prompt fragment establishing the
  content/instruction boundary. Prepended to every agent system prompt.
- `wrap_untrusted(content)` — wraps raw email text in `<<EMAIL_CONTENT>>` /
  `<<END_EMAIL_CONTENT>>` delimiters before showing to the model.

### `safety/guards.py` — addition
- `validate_no_destructive_tools(tool_slugs)` — raises `ValueError` if any
  slug matches destructive markers (DELETE, TRASH, PURGE, BATCH_DELETE, PERMANENT).
  Called at import time in `tools/registry.py` — fails fast before any model call.

### `queue/schema.sql` — addition
- `processed_messages(message_id, action_type, action_id, processed_at)` table.
  Primary key on `(message_id, action_type)` so the same email cannot be
  replied to twice.

### `queue/store.py` — additions
- `mark_message_processed(message_id, action_type, action_id)` — idempotent
  write (`INSERT OR IGNORE`).
- `is_message_processed(message_id, action_type)` — fast primary-key lookup.

### `interfaces/approval_handlers.py` — additions
- `SendApprovalFlow.approve()` and `edit_and_send()` call
  `mark_message_processed` after every successful send (using `source_message_id`
  from the payload, if present).

### `interfaces/slack_app.py` — addition
- Before queuing a `send_email` action: checks `is_message_processed` for the
  `source_message_id`. If already processed, posts "Already replied" and skips.

### `core/agent.py` — additions
- `INJECTION_DEFENSE_PREAMBLE` now heads every system prompt.
- `propose_reply` tool schema gains an optional `source_message_id` field.
- System prompt instructs model to always include `source_message_id`.

## How to run

```
python -m pytest
```
64 tests pass.

## What the tests cover

**Adversarial injection (4 parametrised + 3 specific):**
- Injection text in a command: even if model calls `propose_reply` with an
  attacker's address, result is a PendingAction — `SEND_EMAIL_SLUG` never called.
- `SEND_EMAIL_SLUG` absent from `ALLOWED_TOOL_SLUGS` (structural exclude).
- `wrap_untrusted` places content inside delimiters.
- Injection arriving via a tool result still produces PendingAction, not a send.

**Destructive tool validation:**
- Safe slugs pass validation.
- DELETE, TRASH, PURGE, BATCH_DELETE slugs each raise `ValueError`.

**Message-ID idempotency (store):**
- `mark_and_check_message_processed`, unprocessed returns false.
- Action-type scoped: same message_id for different action_type is independent.
- Duplicate `mark_message_processed` calls are idempotent.

**Approval flow — idempotency (interfaces):**
- Approve records `source_message_id` in `processed_messages`.
- Edit-and-send records `source_message_id`.
- Works correctly when `source_message_id` is absent (no crash).

## Safety invariants now enforced

| Invariant | Mechanism |
|---|---|
| Model can't call send tool | `SEND_EMAIL_SLUG` ∉ `ALLOWED_TOOL_SLUGS` (checked at import) |
| Model can't add destructive tools | `validate_no_destructive_tools` runs at import |
| Email content can't masquerade as instructions | `INJECTION_DEFENSE_PREAMBLE` + `wrap_untrusted` delimiters |
| Same email can't be replied to twice | `processed_messages` table + pre-queue dedup check |
| Action can't be approved twice | `is_pending` check before every approval |
| Non-owner can't approve/send | `is_owner` check in every handler |

## Threading note
Reply-in-thread depends on the Composio send tool accepting `thread_id`. The
current `build_send_email_arguments()` always passes `thread_id` when present.
Verify the confirmed send slug supports this parameter via
`scripts/discover_send_tool.py`.
