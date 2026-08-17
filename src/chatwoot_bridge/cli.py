"""chatwoot-bridge CLI.

chatwoot-bridge ingest <directory>   - ingest a folder of documents
chatwoot-bridge serve                - run the webhook listener
"""

import argparse
import sys
from pathlib import Path

import uvicorn

from chatwoot_bridge.config import build_llm, build_vector_store, load_env
from chatwoot_bridge.memory.ingest import ingest_path


def cmd_ingest(args: argparse.Namespace) -> int:
    env = load_env()
    llm = build_llm(env)
    store = build_vector_store(env, llm)
    stored = ingest_path(args.directory, store=store, llm=llm, max_chars=args.max_chars)
    print(f"stored {stored} chunk(s) from {args.directory}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    uvicorn.run("chatwoot_bridge.api.webhook_listener:app", host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chatwoot-bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="ingest a directory of documents")
    ingest_parser.add_argument("directory", type=Path)
    ingest_parser.add_argument("--max-chars", type=int, default=800)
    ingest_parser.set_defaults(func=cmd_ingest)

    serve_parser = subparsers.add_parser("serve", help="run the webhook listener")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8001)
    serve_parser.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
