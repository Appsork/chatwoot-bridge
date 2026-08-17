"""Shared .env loading and component wiring for entrypoints (webhook listener, CLI)."""

import os
from pathlib import Path

from chatwoot_bridge.connectors.chatwoot import ChatwootConnector
from chatwoot_bridge.llm.openai_compatible import OpenAICompatibleLLM
from chatwoot_bridge.memory.vector_store import VectorStore

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_env(path: Path | None = None) -> dict[str, str]:
    """Parse .env, then let real process environment variables override matching keys.

    This lets docker-compose's `environment:` override values (e.g. hostnames
    that differ inside the container network) without editing .env itself.
    """
    path = path or (REPO_ROOT / ".env")
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    for key in values:
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def build_llm(env: dict[str, str]) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(
        api_base=env["LLM_API_BASE"],
        model=env["LLM_MODEL"],
        api_key=env.get("LLM_API_KEY") or None,
        embedding_model=env.get("EMBEDDING_MODEL"),
    )


def build_connector(env: dict[str, str]) -> ChatwootConnector:
    return ChatwootConnector(
        base_url=env["CHATWOOT_URL"],
        api_token=env["CHATWOOT_API_TOKEN"],
        account_id=int(env["CHATWOOT_ACCOUNT_ID"]),
    )


def build_vector_store(env: dict[str, str], llm: OpenAICompatibleLLM) -> VectorStore:
    embedding_dim = len(llm.embed("dimension probe"))
    store = VectorStore(database_url=env["VECTOR_DB_URL"], embedding_dim=embedding_dim)
    store.ensure_schema()
    return store
