"""LLM access via any OpenAI-compatible chat/embeddings endpoint.

Covers Ollama, OpenAI, DeepSeek, and other providers that speak the
OpenAI /v1/chat/completions and /v1/embeddings request shape. Uses only
the standard library so the bridge carries no HTTP client dependency.
"""

import json
import urllib.error
import urllib.request

from chatwoot_bridge.llm.base import LLMBase

DEFAULT_TIMEOUT_SECONDS = 30.0


class LLMRequestError(RuntimeError):
    """Raised when the OpenAI-compatible endpoint returns an error or bad response."""


class OpenAICompatibleLLM(LLMBase):
    def __init__(
        self,
        api_base: str,
        model: str,
        api_key: str | None = None,
        embedding_model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._embedding_model = embedding_model or model
        self._timeout = timeout

    def ask(self, question: str, context: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": f"Use the following context to answer the question:\n\n{context}",
                },
                {"role": "user", "content": question},
            ],
        }
        response = self._post("/v1/chat/completions", payload)
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMRequestError(f"unexpected chat completion response: {response}") from exc

    def embed(self, text: str) -> list[float]:
        payload = {"model": self._embedding_model, "input": text}
        response = self._post("/v1/embeddings", payload)
        try:
            return response["data"][0]["embedding"]
        except (KeyError, IndexError) as exc:
            raise LLMRequestError(f"unexpected embeddings response: {response}") from exc

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self._api_base}{path}"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMRequestError(f"{url} returned HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise LLMRequestError(f"failed to reach {url}: {exc.reason}") from exc
