"""pgvector-backed storage for document and past-conversation chunks.

Lives in its own database (VECTOR_DB_URL), separate from Chatwoot's own
Postgres database - see ARCHITECTURE.md's Storage section.
"""

from dataclasses import dataclass

import psycopg2


@dataclass
class Chunk:
    id: int
    source: str
    content: str
    distance: float


class VectorStore:
    def __init__(self, database_url: str, embedding_dim: int) -> None:
        self._database_url = database_url
        self._embedding_dim = int(embedding_dim)

    def ensure_schema(self) -> None:
        conn = psycopg2.connect(self._database_url)
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id SERIAL PRIMARY KEY,
                        source TEXT NOT NULL,
                        content TEXT NOT NULL,
                        embedding VECTOR({self._embedding_dim}) NOT NULL
                    )
                    """
                )
            conn.commit()
        finally:
            conn.close()

    def add_chunk(self, source: str, content: str, embedding: list[float]) -> int:
        conn = psycopg2.connect(self._database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO document_chunks (source, content, embedding)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (source, content, _to_vector_literal(embedding)),
                )
                chunk_id = cur.fetchone()[0]
            conn.commit()
            return chunk_id
        finally:
            conn.close()

    def search(self, embedding: list[float], top_n: int = 5) -> list[Chunk]:
        conn = psycopg2.connect(self._database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, source, content, embedding <=> %s AS distance
                    FROM document_chunks
                    ORDER BY distance ASC
                    LIMIT %s
                    """,
                    (_to_vector_literal(embedding), top_n),
                )
                rows = cur.fetchall()
            return [Chunk(id=r[0], source=r[1], content=r[2], distance=r[3]) for r in rows]
        finally:
            conn.close()


def _to_vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(repr(v) for v in embedding) + "]"
