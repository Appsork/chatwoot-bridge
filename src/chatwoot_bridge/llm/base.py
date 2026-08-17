"""Contract every LLM access method must implement.

A new LLM transport (a new provider, MCP, etc.) is added as a new file in
this package that implements LLMBase — core/responder.py is never changed
to accommodate it.
"""

from abc import ABC, abstractmethod


class LLMBase(ABC):
    @abstractmethod
    def ask(self, question: str, context: str) -> str:
        """Answer a question given retrieved context, returning the draft text."""
        raise NotImplementedError

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for a chunk of text."""
        raise NotImplementedError
