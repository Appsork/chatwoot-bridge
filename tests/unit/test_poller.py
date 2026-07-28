import unittest

from chatwoot_bridge.channel_sources.base import ChannelSourceBase
from chatwoot_bridge.connectors.chatwoot import ChatwootConnector
from chatwoot_bridge.core.poller import poll_source
from chatwoot_bridge.core.responder import SAFETY_CHECK_QUESTION
from chatwoot_bridge.llm.base import LLMBase
from chatwoot_bridge.memory.vector_store import Chunk

UNSAFE_MARKER = "unsafe test marker"


class _FakeSource(ChannelSourceBase):
    def __init__(self, items: list[dict]) -> None:
        self._items = items

    def fetch_new_items(self) -> list[dict]:
        return self._items

    def post_reply(self, item_id: str, text: str) -> dict:
        raise NotImplementedError


class _FakeConnector(ChatwootConnector):
    """Records create_contact/create_conversation/post_note calls instead of hitting HTTP."""

    def __init__(self) -> None:
        self.created_contacts: list[dict] = []
        self.created_conversations: list[dict] = []
        self.posted_notes: list[tuple[int, str]] = []
        self._next_contact_id = 1
        self._next_conversation_id = 100

    def create_contact(self, inbox_id: int, name: str, identifier: str) -> dict:
        self.created_contacts.append({"inbox_id": inbox_id, "name": name, "identifier": identifier})
        contact = {"id": self._next_contact_id, "source_id": f"source-{identifier}"}
        self._next_contact_id += 1
        return contact

    def create_conversation(self, inbox_id: int, contact_id: int, source_id: str) -> dict:
        self.created_conversations.append(
            {"inbox_id": inbox_id, "contact_id": contact_id, "source_id": source_id}
        )
        conversation_id = self._next_conversation_id
        self._next_conversation_id += 1
        return {"id": conversation_id}

    def post_note(self, conversation_id: int, content: str) -> dict:
        self.posted_notes.append((conversation_id, content))
        return {"id": conversation_id, "private": True, "content": content}


class _FakeLLM(LLMBase):
    def ask(self, question: str, context: str) -> str:
        if question == SAFETY_CHECK_QUESTION:
            return "yes" if UNSAFE_MARKER in context else "no"
        return f"answer to: {question}"

    def embed(self, text: str) -> list[float]:
        return [0.0]


class _FakeStore:
    def search(self, embedding: list[float], top_n: int = 5) -> list[Chunk]:
        return []


class PollSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = _FakeConnector()
        self.llm = _FakeLLM()
        self.store = _FakeStore()

    def test_poll_source_creates_contact_conversation_and_posts_note(self) -> None:
        source = _FakeSource(
            [{"id": "1", "author": "alice", "text": "a safe story title", "url": "http://example.com/1"}]
        )

        count = poll_source(source, inbox_id=3, connector=self.connector, store=self.store, llm=self.llm)

        self.assertEqual(count, 1)
        self.assertEqual(
            self.connector.created_contacts, [{"inbox_id": 3, "name": "alice", "identifier": "1"}]
        )
        self.assertEqual(len(self.connector.created_conversations), 1)
        self.assertEqual(self.connector.created_conversations[0]["inbox_id"], 3)
        self.assertEqual(len(self.connector.posted_notes), 1)
        conversation_id, note_text = self.connector.posted_notes[0]
        self.assertEqual(note_text, "answer to: a safe story title")

    def test_poll_source_does_not_post_flagged_draft(self) -> None:
        source = _FakeSource(
            [{"id": "2", "author": "bob", "text": UNSAFE_MARKER, "url": "http://example.com/2"}]
        )

        count = poll_source(source, inbox_id=3, connector=self.connector, store=self.store, llm=self.llm)

        self.assertEqual(count, 1)
        self.assertEqual(len(self.connector.created_contacts), 1)
        self.assertEqual(len(self.connector.created_conversations), 1)
        self.assertEqual(self.connector.posted_notes, [])

    def test_poll_source_with_no_new_items_does_nothing(self) -> None:
        source = _FakeSource([])

        count = poll_source(source, inbox_id=3, connector=self.connector, store=self.store, llm=self.llm)

        self.assertEqual(count, 0)
        self.assertEqual(self.connector.created_contacts, [])
        self.assertEqual(self.connector.posted_notes, [])


if __name__ == "__main__":
    unittest.main()
