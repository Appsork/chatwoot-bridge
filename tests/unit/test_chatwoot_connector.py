import io
import json
import unittest
from unittest.mock import patch

from chatwoot_bridge.connectors.base import ConnectorBase
from chatwoot_bridge.connectors.chatwoot import ChatwootConnector, ChatwootRequestError


def _fake_response(payload: dict) -> io.BytesIO:
    body = io.BytesIO(json.dumps(payload).encode("utf-8"))
    body.__enter__ = lambda self=body: self
    body.__exit__ = lambda self, *exc: False
    return body


class ChatwootConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = ChatwootConnector(
            base_url="http://chatwoot.example:3000",
            api_token="test-token",
            account_id=2,
        )

    def test_satisfies_connector_base_contract(self) -> None:
        self.assertIsInstance(self.connector, ConnectorBase)

    @patch("chatwoot_bridge.connectors.chatwoot.urllib.request.urlopen")
    def test_fetch_recent_conversations_returns_payload_list(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response(
            {"data": {"payload": [{"id": 1}, {"id": 2}], "meta": {}}}
        )

        result = self.connector.fetch_recent_conversations(limit=25)

        self.assertEqual(result, [{"id": 1}, {"id": 2}])
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(
            request.full_url,
            "http://chatwoot.example:3000/api/v1/accounts/2/conversations",
        )
        self.assertEqual(request.get_header("Api_access_token"), "test-token")

    @patch("chatwoot_bridge.connectors.chatwoot.urllib.request.urlopen")
    def test_fetch_recent_conversations_returns_empty_list_when_none_exist(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response(
            {"data": {"payload": [], "meta": {"all_count": 0}}}
        )

        result = self.connector.fetch_recent_conversations()

        self.assertEqual(result, [])

    @patch("chatwoot_bridge.connectors.chatwoot.urllib.request.urlopen")
    def test_fetch_conversation_messages_returns_payload_list(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response(
            {"payload": [{"id": 1, "content": "hi"}, {"id": 2, "content": "there"}]}
        )

        result = self.connector.fetch_conversation_messages(conversation_id=7)

        self.assertEqual(result, [{"id": 1, "content": "hi"}, {"id": 2, "content": "there"}])
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(
            request.full_url,
            "http://chatwoot.example:3000/api/v1/accounts/2/conversations/7/messages",
        )

    @patch("chatwoot_bridge.connectors.chatwoot.urllib.request.urlopen")
    def test_post_note_sends_private_flag(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"id": 99, "private": True, "content": "hi"})

        result = self.connector.post_note(conversation_id=7, content="hi")

        self.assertEqual(result["id"], 99)
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(
            request.full_url,
            "http://chatwoot.example:3000/api/v1/accounts/2/conversations/7/messages",
        )
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent, {"content": "hi", "private": True})

    @patch("chatwoot_bridge.connectors.chatwoot.urllib.request.urlopen")
    def test_register_webhook_posts_url_and_subscriptions(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"id": 1, "url": "http://bridge.example/webhook"})

        result = self.connector.register_webhook("http://bridge.example/webhook")

        self.assertEqual(result["url"], "http://bridge.example/webhook")
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(
            request.full_url,
            "http://chatwoot.example:3000/api/v1/accounts/2/webhooks",
        )
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent["url"], "http://bridge.example/webhook")

    @patch("chatwoot_bridge.connectors.chatwoot.urllib.request.urlopen")
    def test_fetch_recent_conversations_raises_on_malformed_response(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"unexpected": "shape"})

        with self.assertRaises(ChatwootRequestError):
            self.connector.fetch_recent_conversations()

    @patch("chatwoot_bridge.connectors.chatwoot.urllib.request.urlopen")
    def test_create_contact_returns_id_and_source_id(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response(
            {
                "payload": {
                    "contact": {"id": 6, "name": "probe-author"},
                    "contact_inbox": {"source_id": "cf4ac0be-fffe-4679-85d0-fff3ed9009c5"},
                }
            }
        )

        result = self.connector.create_contact(inbox_id=3, name="probe-author", identifier="story-1")

        self.assertEqual(result, {"id": 6, "source_id": "cf4ac0be-fffe-4679-85d0-fff3ed9009c5"})
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(
            request.full_url,
            "http://chatwoot.example:3000/api/v1/accounts/2/contacts",
        )
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent, {"inbox_id": 3, "name": "probe-author", "identifier": "story-1"})

    @patch("chatwoot_bridge.connectors.chatwoot.urllib.request.urlopen")
    def test_create_contact_raises_on_malformed_response(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"unexpected": "shape"})

        with self.assertRaises(ChatwootRequestError):
            self.connector.create_contact(inbox_id=3, name="probe-author", identifier="story-1")

    @patch("chatwoot_bridge.connectors.chatwoot.urllib.request.urlopen")
    def test_create_conversation_posts_source_and_returns_id(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"id": 4, "inbox_id": 3, "status": "open"})

        result = self.connector.create_conversation(inbox_id=3, contact_id=6, source_id="cf4ac0be")

        self.assertEqual(result["id"], 4)
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(
            request.full_url,
            "http://chatwoot.example:3000/api/v1/accounts/2/conversations",
        )
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent, {"source_id": "cf4ac0be", "inbox_id": 3, "contact_id": 6})


if __name__ == "__main__":
    unittest.main()
