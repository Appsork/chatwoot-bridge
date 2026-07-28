"""Contract every channel source must implement.

A new channel source (a platform needing only simple config-driven API
calls, or one needing real auth logic like OAuth) is added as a new file
in this package that implements ChannelSourceBase - core/responder.py is
never changed to accommodate it.
"""

from abc import ABC, abstractmethod


class ChannelSourceBase(ABC):
    @abstractmethod
    def fetch_new_items(self) -> list[dict]:
        """Return items not seen by a prior call, each with at least id, author, text, url.

        Input filtering (CLAUDE.md, "Content Safety - Non-negotiable") is
        mandatory here: implementations must reject items containing clear
        child exploitation content, illegal content, or content abusive or
        harassing toward the account owner or others, before an item is
        returned to any caller. When in doubt, exclude rather than include.
        """
        raise NotImplementedError

    @abstractmethod
    def post_reply(self, item_id: str, text: str) -> dict:
        """Post a reply to the item identified by item_id."""
        raise NotImplementedError
