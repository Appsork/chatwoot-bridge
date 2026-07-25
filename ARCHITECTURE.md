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

## Flow

1. Chatwoot sends a webhook when a new message arrives.
2. `api/webhook_listener.py` receives it, hands it to `core/responder.py`.
3. `core/responder.py` asks `memory/retrieve.py` for the most relevant
   documentation and past-conversation matches (pgvector similarity search).
4. It builds one combined prompt and sends it to whichever `llm/` method
   is configured.
5. The drafted answer is posted back to Chatwoot as a private note —
   a human reviews and sends it, never auto-sent.

## Storage

Uses the same PostgreSQL server Chatwoot's own Docker Compose stack
already runs (pgvector extension), but in a separate database — so
Chatwoot's own schema and updates are never affected.
