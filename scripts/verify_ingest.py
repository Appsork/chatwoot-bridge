"""Standalone Phase 3 check: prove memory.ingest works end-to-end against real services.

Creates a small temporary folder of sample docs, ingests it for real
(real embeddings, real pgvector database), confirms the vector store
holds exactly the expected number of chunks, then cleans up after itself.

Usage: python3 scripts/verify_ingest.py
"""

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import psycopg2  # noqa: E402
from _env import load_env  # noqa: E402
from chatwoot_bridge.llm.openai_compatible import OpenAICompatibleLLM  # noqa: E402
from chatwoot_bridge.memory.ingest import ingest_path  # noqa: E402
from chatwoot_bridge.memory.vector_store import VectorStore  # noqa: E402

SAMPLE_DOCS = {
    "refunds.txt": (
        "Refunds are processed within five business days of approval.\n\n"
        "Refund requests must be submitted within 30 days of purchase to qualify."
    ),
    "shipping.txt": (
        "Standard shipping takes 3 to 7 business days depending on destination.\n\n"
        "Expedited shipping is available at checkout for an additional fee."
    ),
    "account.txt": (
        'You can reset your password from the login page using the "Forgot password" link.\n\n'
        "Two-factor authentication can be enabled from account security settings."
    ),
}
MAX_CHARS = 100  # forces each paragraph into its own chunk -> 2 chunks/file
EXPECTED_CHUNKS = len(SAMPLE_DOCS) * 2


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

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for name, content in SAMPLE_DOCS.items():
            (tmp_dir / name).write_text(content)

        print(f"-- ingest_path({tmp_dir}, max_chars={MAX_CHARS}) --")
        stored = ingest_path(tmp_dir, store=store, llm=llm, max_chars=MAX_CHARS)
        print(f"reported: stored {stored} chunk(s)")

        print()
        print("-- verifying against vector_store directly --")
        conn = psycopg2.connect(env["VECTOR_DB_URL"])
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*) FROM document_chunks WHERE source LIKE %s",
            (f"{tmp_dir}%",),
        )
        actual = cur.fetchone()[0]
        print(f"actual rows in document_chunks for this run: {actual}")

        cur.execute("DELETE FROM document_chunks WHERE source LIKE %s", (f"{tmp_dir}%",))
        conn.commit()
        cur.close()
        conn.close()

    print()
    if stored == EXPECTED_CHUNKS and actual == EXPECTED_CHUNKS:
        print(f"RESULT: PASS - {actual} chunks stored, matching expected {EXPECTED_CHUNKS}.")
        return 0

    print(f"RESULT: FAIL - expected {EXPECTED_CHUNKS} chunks, ingest reported {stored}, store had {actual}.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
