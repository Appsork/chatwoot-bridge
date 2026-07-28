"""Polls a channel source for new items and drafts a private-note reply for each.

new item -> create a Chatwoot contact + conversation (connectors/chatwoot.py)
-> core/responder.py's draft_answer() (the same retrieve+ask+safety-check
pipeline already proven for the webhook path) -> posted as a private note
via the existing post_note() - never auto-sent, same as the webhook path.
A flagged draft is never posted, same rule as the webhook path.

Dedup is handled entirely by the channel source's own checkpoint
(channel_sources/checkpoint.py) - fetch_new_items() only ever returns items
not already seen, so polling repeatedly is safe and idempotent.
"""

import logging

from chatwoot_bridge.channel_sources.base import ChannelSourceBase
from chatwoot_bridge.connectors.chatwoot import ChatwootConnector
from chatwoot_bridge.core.responder import draft_answer
from chatwoot_bridge.llm.base import LLMBase
from chatwoot_bridge.memory.vector_store import VectorStore

logger = logging.getLogger("chatwoot_bridge.poller")


def poll_source(
    source: ChannelSourceBase,
    inbox_id: int,
    connector: ChatwootConnector,
    store: VectorStore,
    llm: LLMBase,
) -> int:
    """Fetch new items from one channel source and draft+post a note for each.

    Returns the number of items fetched (not the number successfully posted -
    flagged drafts are counted as fetched but are not posted).
    """
    items = source.fetch_new_items()
    for item in items:
        _process_item(item, inbox_id=inbox_id, connector=connector, store=store, llm=llm)
    return len(items)


def poll_all(sources: list[tuple[ChannelSourceBase, int]], connector: ChatwootConnector, store: VectorStore, llm: LLMBase) -> int:
    """Poll every (channel source, target inbox_id) pair. Returns total items fetched."""
    total = 0
    for source, inbox_id in sources:
        total += poll_source(source, inbox_id=inbox_id, connector=connector, store=store, llm=llm)
    return total


def _process_item(
    item: dict, inbox_id: int, connector: ChatwootConnector, store: VectorStore, llm: LLMBase
) -> None:
    contact = connector.create_contact(inbox_id=inbox_id, name=item["author"] or "unknown", identifier=item["id"])
    conversation = connector.create_conversation(
        inbox_id=inbox_id, contact_id=contact["id"], source_id=contact["source_id"]
    )
    conversation_id = conversation["id"]

    result = draft_answer(item["text"], store=store, llm=llm)

    if result.flagged:
        logger.warning("drafted answer flagged for item %s, not posting", item["id"])
        return

    connector.post_note(conversation_id, result.text)
    logger.info("posted drafted note for item %s in conversation %s", item["id"], conversation_id)
