"""Config-driven channel source for any simple GET-a-list-of-JSON API.

Reads its target URL, optional auth header/value, and field mappings
entirely from the caller (which in practice means .env, via config.py or
a script's own env loader) - no platform-specific code lives here. This
is deliberately limited: it does not handle OAuth flows, token refresh,
or non-JSON responses. Sources needing that get their own file instead
(see channel_sources/base.py).

Assumes the endpoint returns items newest-first (the common convention
for a "recent items" / "search by date" style endpoint) - that ordering
is what lets fetch_new_items() stop as soon as it reaches the previously
seen item.
"""

import json
import urllib.error
import urllib.request

from chatwoot_bridge.channel_sources.base import ChannelSourceBase
from chatwoot_bridge.channel_sources.checkpoint import CheckpointStore

DEFAULT_TIMEOUT_SECONDS = 30.0


class GenericAPIError(RuntimeError):
    """Raised when the configured API returns an error or an unexpected response shape."""


def _resolve_path(data: dict, path: str) -> object:
    """Walk a dotted path ("hits" or "data.items") through nested dicts."""
    value: object = data
    if not path:
        return value
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


class GenericAPIChannelSource(ChannelSourceBase):
    def __init__(
        self,
        source_name: str,
        url: str,
        items_path: str,
        id_field: str,
        text_field: str,
        checkpoint_store: CheckpointStore,
        author_field: str = "",
        url_field: str = "",
        auth_header: str = "",
        auth_value: str = "",
        reply_url: str = "",
        reply_text_field: str = "text",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._source_name = source_name
        self._url = url
        self._items_path = items_path
        self._id_field = id_field
        self._author_field = author_field
        self._text_field = text_field
        self._url_field = url_field
        self._auth_header = auth_header
        self._auth_value = auth_value
        self._reply_url = reply_url
        self._reply_text_field = reply_text_field
        self._checkpoint_store = checkpoint_store
        self._timeout = timeout

    def fetch_new_items(self) -> list[dict]:
        items = [self._map_item(raw) for raw in self._fetch_raw_items()]
        last_seen_id = self._checkpoint_store.get_last_seen_id(self._source_name)

        new_items = []
        for item in items:
            if item["id"] == last_seen_id:
                break
            new_items.append(item)

        if items:
            self._checkpoint_store.set_last_seen_id(self._source_name, items[0]["id"])

        new_items.reverse()  # oldest-new-item first
        return new_items

    def post_reply(self, item_id: str, text: str) -> dict:
        if not self._reply_url:
            raise GenericAPIError(
                f"source {self._source_name!r} has no reply URL configured - read-only source"
            )
        url = self._reply_url.format(item_id=item_id)
        return self._request("POST", url, payload={self._reply_text_field: text})

    def _fetch_raw_items(self) -> list[dict]:
        response = self._request("GET", self._url)
        items = _resolve_path(response, self._items_path)
        if not isinstance(items, list):
            raise GenericAPIError(
                f"items path {self._items_path!r} did not resolve to a list in response from {self._url}"
            )
        return items

    def _map_item(self, raw: dict) -> dict:
        item_id = _resolve_path(raw, self._id_field)
        if item_id is None:
            raise GenericAPIError(f"item missing id field {self._id_field!r}: {raw}")
        return {
            "id": str(item_id),
            "author": str(_resolve_path(raw, self._author_field) or "") if self._author_field else "",
            "text": str(_resolve_path(raw, self._text_field) or ""),
            "url": str(_resolve_path(raw, self._url_field) or "") if self._url_field else "",
        }

    def _request(self, method: str, url: str, payload: dict | None = None) -> dict:
        headers = {}
        if self._auth_header and self._auth_value:
            headers[self._auth_header] = self._auth_value
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise GenericAPIError(f"{method} {url} returned HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise GenericAPIError(f"failed to reach {url}: {exc.reason}") from exc
