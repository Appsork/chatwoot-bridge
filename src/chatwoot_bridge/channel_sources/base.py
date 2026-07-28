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
        """Return items not seen by a prior call, each with at least id, author, text, url."""
        raise NotImplementedError

    @abstractmethod
    def post_reply(self, item_id: str, text: str) -> dict:
        """Post a reply to the item identified by item_id."""
        raise NotImplementedError
