# Setting up chatwoot-bridge

chatwoot-bridge connects your self-hosted Chatwoot instance to any LLM
(Ollama, OpenAI, DeepSeek, or any OpenAI-compatible endpoint) so it can
draft grounded replies from your own documentation and past conversations.

## Required .env values
- CHATWOOT_URL: your Chatwoot instance's address
- CHATWOOT_API_TOKEN: from your Chatwoot profile's Access Token page
- CHATWOOT_ACCOUNT_ID: found via your Chatwoot API token's profile endpoint
- LLM_API_BASE: your LLM endpoint (e.g. http://your-ollama-host:11434)
- VECTOR_DB_URL: a Postgres database with the pgvector extension enabled

## Common setup issues
- If the webhook never fires: check Chatwoot's SafeFetch SSRF guard. If
  chatwoot-bridge and Chatwoot are on the same private network, set
  SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true in Chatwoot's own .env.
- If LLM calls fail after a network change: confirm the LLM host's IP
  hasn't shifted (use a static IP for any machine hosting the LLM).
