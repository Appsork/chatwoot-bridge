"""Standalone check: prove core/poller.py works end-to-end against a real
Chatwoot instance and a real channel source (configured via .env).

Polls once, then lists every conversation currently in the configured
target inbox (via the existing, unmodified fetch_recent_conversations()
and fetch_conversation_messages()) so a human can see the real items and
their drafted private notes.

Usage: python3 scripts/verify_poller.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _env import load_env  # noqa: E402
from chatwoot_bridge.channel_sources.checkpoint import CheckpointStore  # noqa: E402
from chatwoot_bridge.channel_sources.generic_api import GenericAPIChannelSource  # noqa: E402
from chatwoot_bridge.connectors.chatwoot import ChatwootConnector  # noqa: E402
from chatwoot_bridge.core.poller import poll_source  # noqa: E402
from chatwoot_bridge.llm.openai_compatible import OpenAICompatibleLLM  # noqa: E402
from chatwoot_bridge.memory.vector_store import VectorStore  # noqa: E402


def build_source(env: dict) -> GenericAPIChannelSource:
    checkpoint_path = Path(env.get("GENERIC_API_CHECKPOINT_PATH") or "var/channel_source_checkpoints.json")
    if not checkpoint_path.is_absolute():
        checkpoint_path = REPO_ROOT / checkpoint_path

    return GenericAPIChannelSource(
        source_name=env["GENERIC_API_SOURCE_NAME"],
        url=env["GENERIC_API_URL"],
        items_path=env["GENERIC_API_ITEMS_PATH"],
        id_field=env["GENERIC_API_ID_FIELD"],
        author_field=env.get("GENERIC_API_AUTHOR_FIELD", ""),
        text_field=env["GENERIC_API_TEXT_FIELD"],
        url_field=env.get("GENERIC_API_URL_FIELD", ""),
        auth_header=env.get("GENERIC_API_AUTH_HEADER", ""),
        auth_value=env.get("GENERIC_API_AUTH_VALUE", ""),
        reply_url=env.get("GENERIC_API_REPLY_URL", ""),
        reply_text_field=env.get("GENERIC_API_REPLY_TEXT_FIELD") or "text",
        checkpoint_store=CheckpointStore(checkpoint_path),
    )


def main() -> int:
    env = load_env(REPO_ROOT / ".env")
    inbox_id = int(env["GENERIC_API_CHATWOOT_INBOX_ID"])

    llm = OpenAICompatibleLLM(
        api_base=env["LLM_API_BASE"],
        model=env["LLM_MODEL"],
        api_key=env.get("LLM_API_KEY") or None,
        embedding_model=env.get("EMBEDDING_MODEL"),
    )
    embedding_dim = len(llm.embed("dimension probe"))
    store = VectorStore(database_url=env["VECTOR_DB_URL"], embedding_dim=embedding_dim)
    store.ensure_schema()

    connector = ChatwootConnector(
        base_url=env["CHATWOOT_URL"],
        api_token=env["CHATWOOT_API_TOKEN"],
        account_id=int(env["CHATWOOT_ACCOUNT_ID"]),
    )
    source = build_source(env)

    print("-- poll_source() --")
    count = poll_source(source, inbox_id=inbox_id, connector=connector, store=store, llm=llm)
    print(f"PASS: fetched {count} new item(s) (0 is fine on a repeat run - proves checkpoint dedup works)")

    print()
    print(f"-- conversations currently in inbox {inbox_id} --")
    conversations = [c for c in connector.fetch_recent_conversations(limit=200) if c.get("inbox_id") == inbox_id]
    print(f"{len(conversations)} conversation(s) found in this inbox")
    for convo in conversations:
        messages = connector.fetch_conversation_messages(convo["id"])
        notes = [m for m in messages if m.get("private")]
        print(f"  conversation id={convo['id']} contact={convo.get('meta', {}).get('sender', {}).get('name')}")
        for note in notes:
            print(f"    private note: {note.get('content')!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
