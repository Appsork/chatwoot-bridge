# Architecture

chatwoot-bridge is a standalone service. It never modifies Chatwoot's own
code — it only talks to Chatwoot through its public REST API and webhooks,
so Chatwoot's own updates (`docker compose pull && up -d`) always work
unaffected.

## Design principle

Two extension points, each defined as a small contract ("base" class).
Any new integration is a new file that satisfies one of these contracts —
nothing else in the project needs to change.

- **Connectors** (`connectors/`) — how the bridge talks to a chat platform.
  `connectors/base.py` defines the contract; `connectors/chatwoot.py` is
  today's implementation. A future Zendesk or Discord connector is just
  a new file here.
- **LLM methods** (`llm/`) — how the bridge talks to a language model.
  `llm/base.py` defines the contract (accept a question + context, return
  an answer); `llm/openai_compatible.py` covers Ollama, OpenAI, DeepSeek,
  and any OpenAI-compatible endpoint today. A future MCP-based method is
  a new file here, same contract.
- **Channel sources** (`channel_sources/`) — polling for platforms with no
  native Chatwoot channel and no webhook. `channel_sources/base.py`
  defines the contract (`fetch_new_items()`, `post_reply()`).
  `channel_sources/generic_api.py` is a config-driven implementation for
  any simple header-auth JSON API - URL, auth, and field mappings all
  come from `.env`, no code per source. A source needing real auth logic
  (OAuth, token refresh) gets its own file instead, same contract.
  `channel_sources/checkpoint.py` gives every source a shared, per-source
  local record of the last-seen item id, so repeated polls never
  reprocess old items. Every implementation enforces basic content
  safety at fetch time, per CLAUDE.md.

## Flow

Two ways a question reaches `core/responder.py`, converging on the same
retrieve -> ask -> safety-check -> private-note pipeline:

**Webhook path** (Chatwoot's own channels, e.g. a customer message):
1. Chatwoot sends a webhook when a new message arrives.
2. `api/webhook_listener.py` receives it, hands it to `core/responder.py`.

**Poll path** (a `channel_sources/` platform with no native Chatwoot channel
or webhook, e.g. Hacker News, Reddit):
1. `core/poller.py` calls a channel source's `fetch_new_items()`.
2. For each new item, it creates a Chatwoot contact + conversation in that
   source's configured inbox (`connectors/chatwoot.py`), then hands the
   item's text to `core/responder.py` the same way the webhook path does.
   Dedup is the channel source's own checkpoint - no separate tracking
   in the poller.

**Shared pipeline** (both paths):
3. `core/responder.py` asks `memory/retrieve.py` for the most relevant
   documentation and past-conversation matches (pgvector similarity search).
4. It builds one combined prompt and sends it to whichever `llm/` method
   is configured, then runs the draft through a safety check (CLAUDE.md,
   "Content Safety - Non-negotiable", output filtering).
5. An unflagged answer is posted back to Chatwoot as a private note via
   the same `connectors/chatwoot.py` `post_note()` either path uses - a
   human reviews and sends it, never auto-sent. A flagged draft is never
   posted.

## Storage

Uses the same PostgreSQL server Chatwoot's own Docker Compose stack
already runs (pgvector extension), but in a separate database — so
Chatwoot's own schema and updates are never affected.
