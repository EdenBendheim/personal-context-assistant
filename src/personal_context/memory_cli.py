"""Review local memory explicitly; no extraction or message sending."""

import argparse
import json
from pathlib import Path

from .memory import Memory
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Create, correct, inspect, or withdraw cited local memory")
    parser.add_argument("--db", type=Path, required=True, help="Existing imported message database")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("--owner", required=True)
    add.add_argument("--contact", required=True)
    add.add_argument("--kind", choices=("fact", "preference"), required=True)
    update = commands.add_parser("update")
    revoke = commands.add_parser("revoke")
    for command in (update, revoke):
        command.add_argument("id")
        command.add_argument("--expected-revision", type=int, required=True)
    for command in (add, update):
        command.add_argument("--text", required=True)
        command.add_argument("--source", nargs=2, action="append", required=True, metavar=("PROVIDER", "ID"))
    for command in (add, update, revoke):
        command.add_argument("--reason", required=True)
        command.add_argument("--at", help="Timezone-aware effective time; defaults to current UTC time")
    listing = commands.add_parser("list")
    listing.add_argument("--owner", required=True)
    listing.add_argument("--contact", required=True)
    listing.add_argument("--before", required=True)
    listing.add_argument("--limit", type=int, default=10)
    commands.add_parser("history").add_argument("id")
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error("Import messages into an existing database first")
    store = Store(str(args.db))
    try:
        memory = Memory(store)
        if args.command == "add":
            result = memory.create(owner=args.owner, contact=args.contact, kind=args.kind, text=args.text,
                                   sources=args.source, reason=args.reason, at=args.at)
        elif args.command == "update":
            result = memory.revise(args.id, expected_revision=args.expected_revision, text=args.text,
                                   sources=args.source, reason=args.reason, at=args.at)
        elif args.command == "revoke":
            result = memory.revoke(args.id, expected_revision=args.expected_revision, reason=args.reason, at=args.at)
        elif args.command == "history":
            result = memory.history(args.id)
        else:
            result = memory.context(owner=args.owner, contact=args.contact, before=args.before, limit=args.limit)
        print(json.dumps(result, indent=2))
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        store.close()


if __name__ == "__main__":
    main()
