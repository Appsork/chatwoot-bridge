"""Standalone Phase 2 check: prove VectorStore works against the real pgvector database.

Reads VECTOR_DB_URL from .env (not mocked), uses the real embedding model from
Phase 1 to produce real vectors, and confirms round-trip storage + similarity
search against the live database.

Usage: python3 scripts/verify_vector_store.py
"""

import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _env import load_env  # noqa: E402
from chatwoot_bridge.llm.openai_compatible import OpenAICompatibleLLM  # noqa: E402
from chatwoot_bridge.memory.vector_store import VectorStore  # noqa: E402


def main() -> int:
    env = load_env(REPO_ROOT / ".env")

    llm = OpenAICompatibleLLM(
        api_base=env["LLM_API_BASE"],
        model=env["LLM_MODEL"],
        api_key=env.get("LLM_API_KEY") or None,
        embedding_model=env.get("EMBEDDING_MODEL"),
    )

    print(f"VECTOR_DB_URL = {env['VECTOR_DB_URL']}")
    print()

    probe_vector = llm.embed("probe")
    embedding_dim = len(probe_vector)
    print(f"embedding dimension (from live {env.get('EMBEDDING_MODEL')} model): {embedding_dim}")

    store = VectorStore(database_url=env["VECTOR_DB_URL"], embedding_dim=embedding_dim)

    print()
    print("-- ensure_schema() --")
    store.ensure_schema()
    print("PASS: schema ready")

    marker = f"vector-store-check-{uuid.uuid4()}"
    relevant_text = "Refunds are processed within five business days of approval."
    unrelated_text = "The office coffee machine is on the third floor."

    print()
    print("-- add_chunk() --")
    relevant_id = store.add_chunk(source=marker, content=relevant_text, embedding=llm.embed(relevant_text))
    unrelated_id = store.add_chunk(source=marker, content=unrelated_text, embedding=llm.embed(unrelated_text))
    print(f"PASS: inserted chunk ids {relevant_id} and {unrelated_id}")

    print()
    print("-- search() --")
    query_embedding = llm.embed("How long does a refund take?")
    results = store.search(query_embedding, top_n=5)
    own_results = [r for r in results if r.source == marker]

    if not own_results:
        print("FAIL: search returned none of the chunks just inserted")
        return 1

    top = own_results[0]
    print(f"PASS: closest match among ours is chunk {top.id} (distance={top.distance:.4f}): {top.content!r}")

    if top.id != relevant_id:
        print(f"FAIL: expected the refund chunk ({relevant_id}) to rank closest, got {top.id}")
        return 1

    print()
    print("RESULT: PASS - schema, insert, and similarity search all work against the live database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
