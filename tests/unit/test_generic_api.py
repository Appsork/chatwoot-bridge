import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chatwoot_bridge.channel_sources.base import ChannelSourceBase
from chatwoot_bridge.channel_sources.checkpoint import CheckpointStore
from chatwoot_bridge.channel_sources.generic_api import GenericAPIChannelSource, GenericAPIError


def _fake_response(payload: dict) -> io.BytesIO:
    body = io.BytesIO(json.dumps(payload).encode("utf-8"))
    body.__enter__ = lambda self=body: self
    body.__exit__ = lambda self, *exc: False
    return body


HITS = [
    {"objectID": "3", "author": "carol", "title": "third post", "url": "http://example.com/3"},
    {"objectID": "2", "author": "bob", "title": "second post", "url": "http://example.com/2"},
    {"objectID": "1", "author": "alice", "title": "first post", "url": "http://example.com/1"},
]


class GenericAPIChannelSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        checkpoint_path = Path(self._tmpdir.name) / "checkpoints.json"
        self.checkpoint_store = CheckpointStore(checkpoint_path)
        self.source = GenericAPIChannelSource(
            source_name="test-source",
            url="https://api.example.com/items",
            items_path="hits",
            id_field="objectID",
            author_field="author",
            text_field="title",
            url_field="url",
            checkpoint_store=self.checkpoint_store,
        )

    def test_satisfies_channel_source_base_contract(self) -> None:
        self.assertIsInstance(self.source, ChannelSourceBase)

    @patch("chatwoot_bridge.channel_sources.generic_api.urllib.request.urlopen")
    def test_fetch_new_items_maps_fields_on_first_run(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"hits": HITS})

        items = self.source.fetch_new_items()

        self.assertEqual(
            items,
            [
                {"id": "1", "author": "alice", "text": "first post", "url": "http://example.com/1"},
                {"id": "2", "author": "bob", "text": "second post", "url": "http://example.com/2"},
                {"id": "3", "author": "carol", "text": "third post", "url": "http://example.com/3"},
            ],
        )

    @patch("chatwoot_bridge.channel_sources.generic_api.urllib.request.urlopen")
    def test_fetch_new_items_advances_checkpoint(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"hits": HITS})

        self.source.fetch_new_items()

        self.assertEqual(self.checkpoint_store.get_last_seen_id("test-source"), "3")

    @patch("chatwoot_bridge.channel_sources.generic_api.urllib.request.urlopen")
    def test_second_run_with_no_new_items_returns_empty_list(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"hits": HITS})
        self.source.fetch_new_items()

        mock_urlopen.return_value = _fake_response({"hits": HITS})
        second_run_items = self.source.fetch_new_items()

        self.assertEqual(second_run_items, [])

    @patch("chatwoot_bridge.channel_sources.generic_api.urllib.request.urlopen")
    def test_second_run_returns_only_items_newer_than_checkpoint(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"hits": HITS[1:]})  # ids 2, 1
        self.source.fetch_new_items()

        new_hit = {"objectID": "4", "author": "dave", "title": "fourth post", "url": "http://example.com/4"}
        mock_urlopen.return_value = _fake_response({"hits": [new_hit] + HITS[1:]})
        second_run_items = self.source.fetch_new_items()

        self.assertEqual(
            second_run_items,
            [{"id": "4", "author": "dave", "text": "fourth post", "url": "http://example.com/4"}],
        )

    @patch("chatwoot_bridge.channel_sources.generic_api.urllib.request.urlopen")
    def test_items_path_not_a_list_raises(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"hits": {"not": "a list"}})

        with self.assertRaises(GenericAPIError):
            self.source.fetch_new_items()

    def test_post_reply_without_reply_url_raises(self) -> None:
        with self.assertRaises(GenericAPIError):
            self.source.post_reply("1", "hello")

    @patch("chatwoot_bridge.channel_sources.generic_api.urllib.request.urlopen")
    def test_post_reply_posts_formatted_url_with_text_field(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"ok": True})
        source = GenericAPIChannelSource(
            source_name="test-source",
            url="https://api.example.com/items",
            items_path="hits",
            id_field="objectID",
            text_field="title",
            checkpoint_store=self.checkpoint_store,
            reply_url="https://api.example.com/items/{item_id}/reply",
            reply_text_field="body",
        )

        result = source.post_reply("42", "thanks!")

        self.assertEqual(result, {"ok": True})
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://api.example.com/items/42/reply")
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"body": "thanks!"})

    @patch("chatwoot_bridge.channel_sources.generic_api.urllib.request.urlopen")
    def test_auth_header_sent_when_configured(self, mock_urlopen) -> None:
        mock_urlopen.return_value = _fake_response({"hits": []})
        source = GenericAPIChannelSource(
            source_name="test-source",
            url="https://api.example.com/items",
            items_path="hits",
            id_field="objectID",
            text_field="title",
            checkpoint_store=self.checkpoint_store,
            auth_header="Authorization",
            auth_value="Bearer secret",
        )

        source.fetch_new_items()

        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")


class CheckpointStoreTests(unittest.TestCase):
    def test_checkpoint_persists_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoints.json"

            CheckpointStore(path).set_last_seen_id("source-a", "99")
            reloaded = CheckpointStore(path)

            self.assertEqual(reloaded.get_last_seen_id("source-a"), "99")

    def test_unknown_source_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(Path(tmp) / "checkpoints.json")
            self.assertIsNone(store.get_last_seen_id("never-seen"))

    def test_multiple_sources_do_not_collide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(Path(tmp) / "checkpoints.json")
            store.set_last_seen_id("source-a", "1")
            store.set_last_seen_id("source-b", "2")

            self.assertEqual(store.get_last_seen_id("source-a"), "1")
            self.assertEqual(store.get_last_seen_id("source-b"), "2")


if __name__ == "__main__":
    unittest.main()
