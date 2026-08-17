"""Standalone Phase 9b check: prove GenericAPIChannelSource works against a real JSON API.

Reads connection + field-mapping details from .env (not mocked). The same
file works against any simple JSON list API - see .env.example for the
GENERIC_API_* variables.

Usage:
  python3 scripts/verify_generic_api.py fetch
  python3 scripts/verify_generic_api.py reply <item_id> ["reply text"]
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _env import load_env  # noqa: E402
from chatwoot_bridge.channel_sources.checkpoint import CheckpointStore  # noqa: E402
from chatwoot_bridge.channel_sources.generic_api import GenericAPIChannelSource, GenericAPIError  # noqa: E402


def build_source(env: dict) -> GenericAPIChannelSource:
    checkpoint_path = Path(env.get("GENERIC_API_CHECKPOINT_PATH") or "var/channel_source_checkpoints.json")
    if not checkpoint_path.is_absolute():
        checkpoint_path = REPO_ROOT / checkpoint_path

    return GenericAPIChannelSource(
        source_name=env["GENERIC_API_SOURCE_NAME"],
        url=env["GENERIC_API_URL"],
        items_path=env["GENERIC_API_ITEMS_PATH"],
        id_field=env["GENERIC_API_ID_FIELD"],
        author_field=env.get("GENERIC_API_AUTHOR_FIELD", ""),
        text_field=env["GENERIC_API_TEXT_FIELD"],
        url_field=env.get("GENERIC_API_URL_FIELD", ""),
        auth_header=env.get("GENERIC_API_AUTH_HEADER", ""),
        auth_value=env.get("GENERIC_API_AUTH_VALUE", ""),
        reply_url=env.get("GENERIC_API_REPLY_URL", ""),
        reply_text_field=env.get("GENERIC_API_REPLY_TEXT_FIELD") or "text",
        checkpoint_store=CheckpointStore(checkpoint_path),
    )


def run_fetch(source: GenericAPIChannelSource) -> int:
    print("-- fetch_new_items() --")
    try:
        items = source.fetch_new_items()
    except GenericAPIError as exc:
        print(f"FAIL: {exc}")
        return 1

    print(f"PASS: got {len(items)} new item(s) (0 is fine if nothing changed since the last run)")
    for item in items:
        print(f"  - id={item['id']} author={item['author']!r}")
        print(f"    text={item['text']!r}")
        print(f"    url={item['url']}")
    return 0


def run_reply(source: GenericAPIChannelSource, item_id: str, text: str) -> int:
    print(f"-- post_reply(item_id={item_id!r}) --")
    try:
        result = source.post_reply(item_id, text)
    except GenericAPIError as exc:
        print(f"FAIL: {exc}")
        return 1

    print(f"PASS: {result}")
    return 0


def main() -> int:
    env = load_env(REPO_ROOT / ".env")
    source = build_source(env)

    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    command = sys.argv[1]
    if command == "fetch":
        return run_fetch(source)
    if command == "reply":
        if len(sys.argv) < 3:
            print('usage: reply <item_id> ["reply text"]')
            return 1
        item_id = sys.argv[2]
        text = sys.argv[3] if len(sys.argv) > 3 else "chatwoot-bridge generic_api live test reply"
        return run_reply(source, item_id, text)

    print(f"unknown command: {command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
