"""Standalone Phase 6 check: prove draft_answer() works end-to-end against real services.

Ingests a small realistic set of test content (documents + the real
Chatwoot test conversation), asks a related question, and prints the
full question, retrieved context, and drafted answer for human review -
then cleans up all test data.

Usage: python3 scripts/verify_responder.py
"""

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import psycopg2  # noqa: E402
from _env import load_env  # noqa: E402
from chatwoot_bridge.connectors.chatwoot import ChatwootConnector  # noqa: E402
from chatwoot_bridge.core.responder import draft_answer  # noqa: E402
from chatwoot_bridge.llm.openai_compatible import OpenAICompatibleLLM  # noqa: E402
from chatwoot_bridge.memory.ingest import ingest_chatwoot_conversations, ingest_path  # noqa: E402
from chatwoot_bridge.memory.vector_store import VectorStore  # noqa: E402

TEST_DOCS = {
    "refunds.txt": (
        "Refunds are processed within five business days of approval.\n\n"
        "Refund requests must be submitted within 30 days of purchase to qualify."
    ),
    "shipping.txt": "Standard shipping takes 3 to 7 business days depending on destination.",
}
QUESTION = "How long does it take to get a refund after it's approved?"


def main() -> int:
    env = load_env(REPO_ROOT / ".env")

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

    print("-- ingesting test document chunks --")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        tmp_dir_str = str(tmp_dir)
        for name, content in TEST_DOCS.items():
            (tmp_dir / name).write_text(content)
        doc_stored = ingest_path(tmp_dir, store=store, llm=llm)
    print(f"stored {doc_stored} document chunk(s)")

    print()
    print("-- re-ingesting Phase 3 Chatwoot conversation #1 --")
    convo_stored = ingest_chatwoot_conversations(connector, store=store, llm=llm)
    print(f"stored {convo_stored} Chatwoot conversation chunk(s)")

    print()
    print("=" * 70)
    print(f"QUESTION: {QUESTION}")
    print("=" * 70)

    result = draft_answer(QUESTION, store=store, llm=llm, top_n=5)

    print()
    print("RETRIEVED CONTEXT (used to ground the answer):")
    for chunk in result.chunks:
        print(f"  [{chunk.distance:.4f}] source={chunk.source!r}")
        print(f"           content={chunk.content!r}")

    print()
    print(f"DRAFTED ANSWER (flagged={result.flagged}):")
    print(result.text)
    print("=" * 70)

    cleanup(env, tmp_dir_str)

    if doc_stored == 0 or convo_stored == 0:
        print()
        print("FAIL: expected both document and Chatwoot ingestion to store at least one chunk")
        return 1

    print()
    print("RESULT: ingestion + retrieval + drafted answer all completed end-to-end.")
    print("Judge relevance/groundedness from the QUESTION / CONTEXT / ANSWER above.")
    return 0


def cleanup(env: dict, tmp_dir_str: str) -> None:
    conn = psycopg2.connect(env["VECTOR_DB_URL"])
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM document_chunks WHERE source LIKE %s OR source LIKE %s",
        ("chatwoot:%", f"{tmp_dir_str}%"),
    )
    print()
    print(f"(cleanup: removed {cur.rowcount} test row(s))")


if __name__ == "__main__":
    raise SystemExit(main())
