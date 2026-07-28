"""Contract every chat-platform connector must implement.

A new connector (Zendesk, Discord, etc.) is added as a new file in this
package that implements ConnectorBase - core/responder.py is never
changed to accommodate it.
"""

from abc import ABC, abstractmethod


class ConnectorBase(ABC):
    @abstractmethod
    def fetch_recent_conversations(self, limit: int = 25) -> list[dict]:
        """Return recent conversations as raw platform records.

        Input filtering (CLAUDE.md, "Content Safety - Non-negotiable") is
        mandatory here: implementations must reject conversations containing
        clear child exploitation content, illegal content, or content abusive
        or harassing toward the account owner or others, before a
        conversation is returned to any caller. When in doubt, exclude
        rather than include.
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_conversation_messages(self, conversation_id: int) -> list[dict]:
        """Return the full message history for one conversation.

        Same input-filtering requirement as fetch_recent_conversations()
        applies to individual messages here.
        """
        raise NotImplementedError

    @abstractmethod
    def create_contact(self, inbox_id: int, name: str, identifier: str) -> dict:
        """Create a contact attached to inbox_id, identified by a caller-chosen unique identifier.

        Used by core/poller.py to represent an external item's author as a
        contact before a conversation can be created for it.
        """
        raise NotImplementedError

    @abstractmethod
    def create_conversation(self, inbox_id: int, contact_id: int, source_id: str) -> dict:
        """Create a new conversation in inbox_id for an existing contact.

        Used by core/poller.py after create_contact() to open a conversation
        for a polled item, before post_note() drafts a reply into it.
        """
        raise NotImplementedError

    @abstractmethod
    def post_note(self, conversation_id: int, content: str) -> dict:
        """Post a private note (never auto-sent to the customer) to a conversation."""
        raise NotImplementedError

    @abstractmethod
    def register_webhook(self, callback_url: str) -> dict:
        """Register callback_url to receive this platform's message events."""
        raise NotImplementedError
