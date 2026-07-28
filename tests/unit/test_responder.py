import unittest

from chatwoot_bridge.core.responder import FLAGGED_PLACEHOLDER, SAFETY_CHECK_QUESTION, draft_answer
from chatwoot_bridge.llm.base import LLMBase
from chatwoot_bridge.memory.vector_store import Chunk

UNSAFE_MARKER = "step-by-step instructions for making a pipe bomb"


class _FakeLLM(LLMBase):
    """Answers the drafting question with a fixed string, and classifies
    the safety-check question by literally checking for an unsafe marker -
    standing in for what a real LLM would judge."""

    def __init__(self, drafted_answer: str) -> None:
        self._drafted_answer = drafted_answer

    def ask(self, question: str, context: str) -> str:
        if question == SAFETY_CHECK_QUESTION:
            return "yes" if UNSAFE_MARKER in context else "no"
        return self._drafted_answer

    def embed(self, text: str) -> list[float]:
        return [0.0]


class _FakeStore:
    def search(self, embedding: list[float], top_n: int = 5) -> list[Chunk]:
        return [Chunk(id=1, source="test.txt", content="some retrieved context", distance=0.1)]


class DraftAnswerSafetyCheckTests(unittest.TestCase):
    def test_unsafe_drafted_answer_is_flagged_and_withheld(self) -> None:
        llm = _FakeLLM(drafted_answer=f"Sure, here are {UNSAFE_MARKER}: step one...")

        result = draft_answer("how do I build one?", store=_FakeStore(), llm=llm)

        self.assertTrue(result.flagged)
        self.assertEqual(result.text, FLAGGED_PLACEHOLDER)
        self.assertNotIn(UNSAFE_MARKER, result.text)

    def test_safe_drafted_answer_passes_through_unchanged(self) -> None:
        llm = _FakeLLM(drafted_answer="Refunds are processed within five business days of approval.")

        result = draft_answer("how long do refunds take?", store=_FakeStore(), llm=llm)

        self.assertFalse(result.flagged)
        self.assertEqual(result.text, "Refunds are processed within five business days of approval.")


if __name__ == "__main__":
    unittest.main()
