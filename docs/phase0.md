# Phase 0 Design Note

Decisions below were verified against current docs before scaffolding. Source links
are in this conversation's record; re-verify if anything here looks stale.

## NVIDIA NIM (reasoning model)

- Confirmed model ID: `mistralai/mistral-nemotron` (matches `.env.example`, no change
  needed). Fallback stays `meta/llama-3.3-70b-instruct`.
- Endpoint `https://integrate.api.nvidia.com/v1` is OpenAI-compatible; use the OpenAI
  Python SDK (`base_url` override) with `tools=[...]` for function calling.
- Free tier: ~1,000 credits, 40 requests/min — `core/loop.py` and Phase 6 must handle
  429 with backoff.

## Composio: SDK chosen over Tool Router

**Decision:** use the Composio **Python SDK directly** (`composio.tools.get()` /
`composio.tools.execute()`), not the Tool Router / MCP endpoint.

**Why:** CLAUDE.md §3 requires a custom NIM tool-calling loop where `tools/registry.py`
exposes a *curated* set of OpenAI-format schemas (read-only Gmail tools only in Phase 1,
no destructive tools per §4.4). The SDK's `tools.get(toolkits=[...])` lets us fetch and
filter schemas per toolkit, and `tools.execute(slug, user_id=..., arguments=...)` maps
1:1 onto `tools/composio_bridge.py`. The Tool Router/MCP endpoint hands a client an
open-ended, dynamically-served tool surface — better suited to MCP-native clients
(Claude Desktop, Cursor) than to a hand-rolled loop where we need fine-grained,
auditable control over exactly which tools the model can see.

**Practical details:**
- Package: `composio` (core SDK), `pip install composio`. Requires Python >=3.10
  (project uses 3.13).
- Toolkit slugs: `GMAIL`, `GOOGLECALENDAR`, `SLACK`.
- Auth: one-time per toolkit via `composio.connected_accounts.link(user_id, auth_config_id)`
  → visit `redirect_url` to complete OAuth. Auth configs are created on
  https://dashboard.composio.dev/~/project/auth-configs. A single personal `user_id`
  (e.g. `"default"`) is sufficient for this project.
- Execution: `composio.tools.execute("GMAIL_FETCH_EMAILS", user_id="default", arguments={...})`.
- Exact action slugs for read tools (e.g. `GMAIL_FETCH_EMAILS`, `GMAIL_GET_THREAD`) must
  be re-verified at Phase 1 against `composio.tools.get(user_id="default", toolkits=["GMAIL"])`
  output — do not hardcode from memory.

## Slack Bolt (Socket Mode)

- `from slack_bolt import App; from slack_bolt.adapter.socket_mode import SocketModeHandler`
- `App(token=SLACK_BOT_TOKEN)` then `SocketModeHandler(app, SLACK_APP_TOKEN).start()`.
- App-level token (`xapp-...`) needs `connections:write`, generated under
  *Basic Information → App-Level Tokens*. Bot token (`xoxb-...`) needs `chat:write` at
  minimum for the smoke test's echo.

## CLAUDE.md updates made

- §6 "Open decisions" updated: Composio SDK chosen (see above), model ID confirmed.
