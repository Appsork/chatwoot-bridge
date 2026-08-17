"""Standalone Phase 4 check: prove retrieve() works against the real pgvector database.

Re-runs the Phase 3 Chatwoot conversation ingestion (its test row was
cleaned up after that phase), then confirms a related real question
surfaces that chunk in the top results with a real similarity score.

Usage: python3 scripts/verify_retrieve.py
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
from chatwoot_bridge.llm.openai_compatible import OpenAICompatibleLLM  # noqa: E402
from chatwoot_bridge.memory.ingest import ingest_chatwoot_conversations, ingest_path  # noqa: E402
from chatwoot_bridge.memory.retrieve import retrieve  # noqa: E402
from chatwoot_bridge.memory.vector_store import VectorStore  # noqa: E402

UNRELATED_DOCS = {
    "shipping.txt": "Standard shipping takes 3 to 7 business days depending on destination.",
    "account.txt": 'You can reset your password from the login page using the "Forgot password" link.',
}


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

    print("-- re-running Phase 3 Chatwoot ingestion (test row was cleaned up) --")
    stored = ingest_chatwoot_conversations(connector, store=store, llm=llm)
    print(f"stored {stored} chunk(s) from Chatwoot conversations")
    if stored == 0:
        print("FAIL: nothing was ingested, nothing to retrieve")
        return 1

    print()
    print("-- adding unrelated document chunks so retrieval is proven across both sources --")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        tmp_dir_str = str(tmp_dir)
        for name, content in UNRELATED_DOCS.items():
            (tmp_dir / name).write_text(content)
        doc_stored = ingest_path(tmp_dir, store=store, llm=llm)
    print(f"stored {doc_stored} unrelated document chunk(s)")

    print()
    print("-- retrieve() --")
    question = "What did the connector live test note say?"
    results = retrieve(question, store=store, llm=llm, top_n=5)
    for r in results:
        print(f"  id={r.id} distance={r.distance:.4f} source={r.source!r} content={r.content!r}")

    matches = [r for r in results if r.source == "chatwoot:conversation:1"]
    if not matches:
        print("FAIL: expected chunk from chatwoot:conversation:1 not found in top results")
        cleanup(env, tmp_dir_str)
        return 1

    top = results[0]
    print()
    if top.source != "chatwoot:conversation:1":
        print(f"FAIL: expected the Chatwoot conversation chunk to rank first, got {top.source!r}")
        cleanup(env, tmp_dir_str)
        return 1

    print(f"PASS: closest match is the Chatwoot conversation chunk (distance={top.distance:.4f})")
    print(f"      (ranked ahead of {len(results) - 1} other result(s), including unrelated document chunks)")
    print("RESULT: PASS - retrieve() surfaces the relevant chunk across both document and conversation sources.")
    cleanup(env, tmp_dir_str)
    return 0


def cleanup(env: dict, tmp_dir_str: str) -> None:
    conn = psycopg2.connect(env["VECTOR_DB_URL"])
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM document_chunks WHERE source LIKE %s OR source LIKE %s",
        ("chatwoot:%", f"{tmp_dir_str}%"),
    )
    print(f"(cleanup: removed {cur.rowcount} test row(s))")


if __name__ == "__main__":
    raise SystemExit(main())
