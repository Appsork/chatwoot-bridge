import io
import json
import unittest
from unittest.mock import patch

from chatwoot_bridge.llm.base import LLMBase
from chatwoot_bridge.llm.openai_compatible import LLMRequestError, OpenAICompatibleLLM


def _fake_response(payload: dict) -> io.BytesIO:
    body = io.BytesIO(json.dumps(payload).encode("utf-8"))
    body.__enter__ = lambda self=body: self
    body.__exit__ = lambda self, *exc: False
    return body


class OpenAICompatibleLLMTests(unittest.TestCase):
    def setUp(self) -> None:
        self.llm = OpenAICompatibleLLM(
            api_base="http://example.local:11434",
            model="llama3.2",
            embedding_model="nomic-embed-text",
        )

    def test_satisfies_llm_base_contract(self) -> None:
        self.assertIsInstance(self.llm, LLMBase)

    @patch("chatwoot_bridge.llm.openai_compatible.urllib.request.urlopen")
    def test_ask_returns_message_content(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response(
            {"choices": [{"message": {"content": "the answer"}}]}
        )

        result = self.llm.ask("what is it?", context="some doc chunk")

        self.assertEqual(result, "the answer")
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "http://example.local:11434/v1/chat/completions")
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent["model"], "llama3.2")
        self.assertEqual(sent["messages"][-1], {"role": "user", "content": "what is it?"})

    @patch("chatwoot_bridge.llm.openai_compatible.urllib.request.urlopen")
    def test_embed_returns_vector(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"data": [{"embedding": [0.1, 0.2, 0.3]}]})

        result = self.llm.embed("some text")

        self.assertEqual(result, [0.1, 0.2, 0.3])
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "http://example.local:11434/v1/embeddings")
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent["model"], "nomic-embed-text")

    @patch("chatwoot_bridge.llm.openai_compatible.urllib.request.urlopen")
    def test_ask_raises_on_malformed_response(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"unexpected": "shape"})

        with self.assertRaises(LLMRequestError):
            self.llm.ask("question", context="context")


if __name__ == "__main__":
    unittest.main()
