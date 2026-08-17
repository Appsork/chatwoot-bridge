"""CLI: load documents or past Chatwoot conversations, chunk, embed, and store them.

python -m chatwoot_bridge.memory.ingest <directory>   # documents
python -m chatwoot_bridge.memory.ingest --chatwoot     # past conversations

Configuration (LLM + vector store + Chatwoot connection) comes from .env,
same variables used by scripts/verify_*.py.
"""

import argparse
import sys
from pathlib import Path

from chatwoot_bridge.connectors.base import ConnectorBase
from chatwoot_bridge.connectors.chatwoot import ChatwootConnector
from chatwoot_bridge.llm.base import LLMBase
from chatwoot_bridge.llm.openai_compatible import OpenAICompatibleLLM
from chatwoot_bridge.memory.vector_store import VectorStore

DOC_EXTENSIONS = (".txt", ".md")

# Chatwoot message_type values that carry real conversation text -
# excludes activity/system log entries (message_type 2).
INCOMING_MESSAGE = 0
OUTGOING_MESSAGE = 1


def chunk_text(text: str, max_chars: int = 800) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def ingest_path(directory: Path, store: VectorStore, llm: LLMBase, max_chars: int = 800) -> int:
    stored = 0
    for file_path in sorted(directory.iterdir()):
        if file_path.suffix.lower() not in DOC_EXTENSIONS:
            continue
        text = file_path.read_text()
        for chunk in chunk_text(text, max_chars=max_chars):
            embedding = llm.embed(chunk)
            store.add_chunk(source=str(file_path), content=chunk, embedding=embedding)
            stored += 1
    return stored


def _conversation_text(messages: list[dict]) -> str:
    lines = []
    for message in messages:
        if message.get("message_type") not in (INCOMING_MESSAGE, OUTGOING_MESSAGE):
            continue
        content = (message.get("content") or "").strip()
        if content:
            lines.append(content)
    return "\n\n".join(lines)


def ingest_chatwoot_conversations(
    connector: ConnectorBase, store: VectorStore, llm: LLMBase, max_chars: int = 800
) -> int:
    stored = 0
    for conversation in connector.fetch_recent_conversations():
        messages = connector.fetch_conversation_messages(conversation["id"])
        text = _conversation_text(messages)
        if not text:
            continue
        source = f"chatwoot:conversation:{conversation['id']}"
        for chunk in chunk_text(text, max_chars=max_chars):
            embedding = llm.embed(chunk)
            store.add_chunk(source=source, content=chunk, embedding=embedding)
            stored += 1
    return stored


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest documents or past Chatwoot conversations into the vector store"
    )
    parser.add_argument("directory", type=Path, nargs="?", default=None)
    parser.add_argument("--chatwoot", action="store_true", help="ingest past Chatwoot conversations instead")
    parser.add_argument("--max-chars", type=int, default=800)
    args = parser.parse_args(argv)

    if args.chatwoot == (args.directory is not None):
        parser.error("pass exactly one of: a directory, or --chatwoot")

    repo_root = Path(__file__).resolve().parents[3]
    env = _load_env(repo_root / ".env")

    llm = OpenAICompatibleLLM(
        api_base=env["LLM_API_BASE"],
        model=env["LLM_MODEL"],
        api_key=env.get("LLM_API_KEY") or None,
        embedding_model=env.get("EMBEDDING_MODEL"),
    )
    embedding_dim = len(llm.embed("dimension probe"))
    store = VectorStore(database_url=env["VECTOR_DB_URL"], embedding_dim=embedding_dim)
    store.ensure_schema()

    if args.chatwoot:
        connector = ChatwootConnector(
            base_url=env["CHATWOOT_URL"],
            api_token=env["CHATWOOT_API_TOKEN"],
            account_id=int(env["CHATWOOT_ACCOUNT_ID"]),
        )
        stored = ingest_chatwoot_conversations(connector, store=store, llm=llm, max_chars=args.max_chars)
        print(f"stored {stored} chunk(s) from Chatwoot conversations")
    else:
        stored = ingest_path(args.directory, store=store, llm=llm, max_chars=args.max_chars)
        print(f"stored {stored} chunk(s) from {args.directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
