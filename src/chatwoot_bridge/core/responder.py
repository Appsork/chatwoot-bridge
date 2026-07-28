"""Orchestrates retrieve() + ask() into one drafted answer for a question.

question -> memory.retrieve() for relevant chunks -> llm.ask() with that
context -> drafted answer. Before being returned, the draft is passed
through a safety check (CLAUDE.md, "Content Safety - Non-negotiable",
output filtering) - a flagged draft is never posted anywhere, including
as a private note. The drafted answer is posted as a private note by
whichever connector/webhook code calls this - never auto-sent.
"""

import logging
from dataclasses import dataclass

from chatwoot_bridge.llm.base import LLMBase
from chatwoot_bridge.memory.retrieve import retrieve
from chatwoot_bridge.memory.vector_store import Chunk, VectorStore

logger = logging.getLogger("chatwoot_bridge.responder")

FLAGGED_PLACEHOLDER = "flagged, not posted"

SAFETY_CHECK_QUESTION = (
    "Does this response contain harassment, illegal content, or directly "
    "fulfill a harmful or dangerous request rather than declining it? "
    "Answer only yes or no."
)


@dataclass
class DraftResult:
    text: str
    chunks: list[Chunk]
    flagged: bool


def draft_answer(question: str, store: VectorStore, llm: LLMBase, top_n: int = 5) -> DraftResult:
    context_chunks = retrieve(question, store=store, llm=llm, top_n=top_n)
    context = "\n\n".join(chunk.content for chunk in context_chunks)
    answer = llm.ask(question, context=context)

    if _is_unsafe(answer, llm=llm):
        logger.warning("drafted answer flagged by safety check for question %r - not posted", question)
        return DraftResult(text=FLAGGED_PLACEHOLDER, chunks=context_chunks, flagged=True)

    return DraftResult(text=answer, chunks=context_chunks, flagged=False)


def _is_unsafe(answer: str, llm: LLMBase) -> bool:
    verdict = llm.ask(SAFETY_CHECK_QUESTION, context=answer)
    return verdict.strip().lower().startswith("yes")
