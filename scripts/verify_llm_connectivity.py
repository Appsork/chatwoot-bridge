"""Standalone Phase 1 check: prove OpenAICompatibleLLM works against a real endpoint.

Reads connection details from .env (not mocked) and exercises both methods
of the LLMBase contract - ask() and embed() - against the live server.

Usage: python3 scripts/verify_llm_connectivity.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from _env import load_env  # noqa: E402
from chatwoot_bridge.llm.openai_compatible import LLMRequestError, OpenAICompatibleLLM  # noqa: E402


def main() -> int:
    env = load_env(REPO_ROOT / ".env")

    llm = OpenAICompatibleLLM(
        api_base=env["LLM_API_BASE"],
        model=env["LLM_MODEL"],
        api_key=env.get("LLM_API_KEY") or None,
        embedding_model=env.get("EMBEDDING_MODEL"),
    )

    print(f"LLM_API_BASE   = {env['LLM_API_BASE']}")
    print(f"LLM_MODEL      = {env['LLM_MODEL']}")
    print(f"EMBEDDING_MODEL = {env.get('EMBEDDING_MODEL')}")
    print()

    ask_ok = False
    embed_ok = False

    print("-- ask() --")
    try:
        answer = llm.ask(
            "Reply with exactly one word: pong",
            context="This is a connectivity check. No document context is relevant.",
        )
        print(f"PASS: got response: {answer!r}")
        ask_ok = True
    except LLMRequestError as exc:
        print(f"FAIL: {exc}")

    print()
    print("-- embed() --")
    try:
        vector = llm.embed("connectivity check")
        print(f"PASS: got {len(vector)}-dim vector, first values: {vector[:5]}")
        embed_ok = True
    except LLMRequestError as exc:
        print(f"FAIL: {exc}")

    print()
    if ask_ok and embed_ok:
        print("RESULT: PASS - both ask() and embed() succeeded against the live endpoint.")
        return 0

    print("RESULT: FAIL - see above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
