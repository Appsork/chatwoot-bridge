"""Given a question, return the top-N most relevant stored chunks.

Searches across all chunks in the vector store regardless of source -
document-derived and Chatwoot-conversation-derived chunks are stored
identically (see memory/ingest.py), so no source-type filtering is needed.
"""

from chatwoot_bridge.llm.base import LLMBase
from chatwoot_bridge.memory.vector_store import Chunk, VectorStore


def retrieve(question: str, store: VectorStore, llm: LLMBase, top_n: int = 5) -> list[Chunk]:
    question_embedding = llm.embed(question)
    return store.search(question_embedding, top_n=top_n)
