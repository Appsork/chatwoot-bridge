"""Standalone Phase 5 check: prove ChatwootConnector works against a real Chatwoot instance.

Reads connection details from .env (not mocked).

Usage:
  python3 scripts/verify_chatwoot_connector.py fetch
  python3 scripts/verify_chatwoot_connector.py post-note <conversation_id> ["note text"]
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _env import load_env  # noqa: E402
from chatwoot_bridge.connectors.chatwoot import ChatwootConnector, ChatwootRequestError  # noqa: E402


def build_connector(env: dict) -> ChatwootConnector:
    return ChatwootConnector(
        base_url=env["CHATWOOT_URL"],
        api_token=env["CHATWOOT_API_TOKEN"],
        account_id=int(env["CHATWOOT_ACCOUNT_ID"]),
    )


def run_fetch(connector: ChatwootConnector) -> int:
    print("-- fetch_recent_conversations() --")
    try:
        conversations = connector.fetch_recent_conversations()
    except ChatwootRequestError as exc:
        print(f"FAIL: {exc}")
        return 1

    print(f"PASS: got a list with {len(conversations)} conversation(s) (empty is fine, no crash)")
    for convo in conversations:
        print(f"  - id={convo.get('id')} status={convo.get('status')}")
    return 0


def run_post_note(connector: ChatwootConnector, conversation_id: int, text: str) -> int:
    print(f"-- post_note(conversation_id={conversation_id}) --")
    try:
        result = connector.post_note(conversation_id, text)
    except ChatwootRequestError as exc:
        print(f"FAIL: {exc}")
        return 1

    print(f"PASS: created message id={result.get('id')} private={result.get('private')}")
    print(f"content sent: {text!r}")
    return 0


def main() -> int:
    env = load_env(REPO_ROOT / ".env")
    connector = build_connector(env)

    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    command = sys.argv[1]
    if command == "fetch":
        return run_fetch(connector)
    if command == "post-note":
        if len(sys.argv) < 3:
            print("usage: post-note <conversation_id> [\"note text\"]")
            return 1
        conversation_id = int(sys.argv[2])
        text = sys.argv[3] if len(sys.argv) > 3 else "chatwoot-bridge connector live test note"
        return run_post_note(connector, conversation_id, text)

    print(f"unknown command: {command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
