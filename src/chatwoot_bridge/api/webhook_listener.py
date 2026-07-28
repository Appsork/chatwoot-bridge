"""FastAPI endpoint that receives Chatwoot's webhook events.

For each new, non-private, customer ("incoming") message, drafts an
answer via core/responder.py and posts it back to the same conversation
as a private note via ChatwootConnector.post_note() - never auto-sent.
A draft flagged by responder.py's safety check is never posted.
Our own posted private notes and agent replies are ignored so the
bridge never responds to its own output.

Run with: uvicorn chatwoot_bridge.api.webhook_listener:app --host 0.0.0.0 --port 8001
"""

import logging

from fastapi import FastAPI, Request

from chatwoot_bridge.config import build_connector, build_llm, build_vector_store, load_env
from chatwoot_bridge.core.responder import draft_answer

logger = logging.getLogger("chatwoot_bridge.webhook_listener")

app = FastAPI()

_env = load_env()
_llm = build_llm(_env)
_store = build_vector_store(_env, _llm)
_connector = build_connector(_env)


def is_new_customer_message(payload: dict) -> bool:
    return (
        payload.get("event") == "message_created"
        and payload.get("message_type") == "incoming"
        and not payload.get("private", False)
    )


@app.post("/webhooks/chatwoot")
async def handle_chatwoot_webhook(request: Request) -> dict:
    payload = await request.json()
    logger.info("received webhook event=%s message_type=%s", payload.get("event"), payload.get("message_type"))

    if not is_new_customer_message(payload):
        return {"status": "ignored"}

    conversation_id = payload["conversation"]["id"]
    question = payload.get("content") or ""

    try:
        result = draft_answer(question, store=_store, llm=_llm)
    except Exception:
        logger.exception("failed to draft answer for conversation %s", conversation_id)
        return {"status": "error"}

    if result.flagged:
        logger.warning("drafted answer flagged by safety check, not posting for conversation %s", conversation_id)
        return {"status": "flagged"}

    try:
        _connector.post_note(conversation_id, result.text)
    except Exception:
        logger.exception("failed to post answer for conversation %s", conversation_id)
        return {"status": "error"}

    return {"status": "drafted"}
