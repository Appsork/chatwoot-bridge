"""Connector for Chatwoot's own public REST API.

Talks to Chatwoot only through documented HTTP endpoints, authenticated
with an agent's api_access_token - never touches Chatwoot's database or
source directly.
"""

import json
import urllib.error
import urllib.request

from chatwoot_bridge.connectors.base import ConnectorBase

DEFAULT_TIMEOUT_SECONDS = 30.0


class ChatwootRequestError(RuntimeError):
    """Raised when the Chatwoot API returns an error or an unexpected response."""


class ChatwootConnector(ConnectorBase):
    def __init__(
        self,
        base_url: str,
        api_token: str,
        account_id: int,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._account_id = account_id
        self._timeout = timeout

    def fetch_recent_conversations(self, limit: int = 25) -> list[dict]:
        response = self._request(
            "GET", f"/api/v1/accounts/{self._account_id}/conversations"
        )
        try:
            conversations = response["data"]["payload"]
        except (KeyError, TypeError) as exc:
            raise ChatwootRequestError(f"unexpected conversations response: {response}") from exc
        return conversations[:limit]

    def fetch_conversation_messages(self, conversation_id: int) -> list[dict]:
        response = self._request(
            "GET", f"/api/v1/accounts/{self._account_id}/conversations/{conversation_id}/messages"
        )
        try:
            return response["payload"]
        except KeyError as exc:
            raise ChatwootRequestError(f"unexpected messages response: {response}") from exc

    def create_contact(self, inbox_id: int, name: str, identifier: str) -> dict:
        response = self._request(
            "POST",
            f"/api/v1/accounts/{self._account_id}/contacts",
            payload={"inbox_id": inbox_id, "name": name, "identifier": identifier},
        )
        try:
            return {
                "id": response["payload"]["contact"]["id"],
                "source_id": response["payload"]["contact_inbox"]["source_id"],
            }
        except (KeyError, TypeError) as exc:
            raise ChatwootRequestError(f"unexpected create contact response: {response}") from exc

    def create_conversation(self, inbox_id: int, contact_id: int, source_id: str) -> dict:
        return self._request(
            "POST",
            f"/api/v1/accounts/{self._account_id}/conversations",
            payload={"source_id": source_id, "inbox_id": inbox_id, "contact_id": contact_id},
        )

    def post_note(self, conversation_id: int, content: str) -> dict:
        return self._request(
            "POST",
            f"/api/v1/accounts/{self._account_id}/conversations/{conversation_id}/messages",
            payload={"content": content, "private": True},
        )

    def register_webhook(self, callback_url: str) -> dict:
        return self._request(
            "POST",
            f"/api/v1/accounts/{self._account_id}/webhooks",
            payload={"url": callback_url, "subscriptions": ["conversation_created", "message_created"]},
        )

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"{self._base_url}{path}"
        headers = {"api_access_token": self._api_token}
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
            raise ChatwootRequestError(f"{method} {url} returned HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise ChatwootRequestError(f"failed to reach {url}: {exc.reason}") from exc
