"""Local last-seen-item checkpoint, shared by every channel_sources implementation.

Keyed by source name so multiple configured sources (Reddit, a generic
API instance, etc.) can share one checkpoint file without colliding.
"""

import json
from pathlib import Path


class CheckpointStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get_last_seen_id(self, source_name: str) -> str | None:
        return self._read().get(source_name)

    def set_last_seen_id(self, source_name: str, item_id: str) -> None:
        data = self._read()
        data[source_name] = item_id
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))

    def _read(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text())
