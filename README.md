# chatwoot-bridge
Connects Chatwoot to any LLM (Ollama, OpenAI, DeepSeek, etc.) for AI-assisted replies using your own docs and past conversations. Independent project, not affiliated with Chatwoot.

## Setup

See [`docs/setup.md`](docs/setup.md) for required `.env` values and
first-run instructions, and [`docs/troubleshooting.md`](docs/troubleshooting.md)
for common issues.

## Project structure

- `src/chatwoot_bridge/` — the service (connectors, LLM access, memory/RAG, orchestration, webhook API)
- `docs/` — setup and troubleshooting docs
- `scripts/` — standalone scripts for verifying each piece of the stack against a real endpoint
- `tests/` — unit tests

## Webhook delivery and private networks

Chatwoot's webhook delivery (`WebhookJob`) runs every webhook URL through
`SafeFetch`, which rejects any URL resolving to a private IP address
unless `SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true` is set on the Chatwoot
side. Whether you need this depends on your deployment:

1. **Chatwoot self-hosted + chatwoot-bridge on the same private network**
   (e.g. same LAN, same Docker host) - requires
   `SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true` in Chatwoot's own `.env`
   (`rails` and `sidekiq` services), applied with `docker compose up -d
   rails sidekiq` (a plain `restart` does not pick up new env vars).
2. **Chatwoot self-hosted + chatwoot-bridge on a public server** (VPS,
   domain name) - no special setting needed.
3. **Chatwoot Cloud + chatwoot-bridge on a public server** - no special
   setting needed.
4. **Chatwoot Cloud + chatwoot-bridge on a private network** - not
   possible. Chatwoot Cloud's SSRF guard cannot be disabled by an
   individual customer, so chatwoot-bridge must be publicly reachable
   in this case.

`SAFE_FETCH_ALLOW_PRIVATE_NETWORK` is not webhook-specific - it is a
single shared toggle that also loosens SSRF protection for Chatwoot's
avatar-from-URL, website-branding-fetch, and upload-by-URL features.
Evaluate your own threat model (multi-user instance vs. a trusted
single-user/admin instance) before enabling it, rather than treating it
as a webhook-only setting.

**Development notes:** Parts of this project were developed with
the assistance of AI coding tools.

This software is provided "as is," without warranty of any kind,
per the MIT License below. Review and test it in your own
environment before relying on it in production.
