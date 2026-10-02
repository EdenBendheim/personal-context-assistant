import argparse
import json
from pathlib import Path
import sqlite3

from .imports import plan_import
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Import exports and inspect recipient-specific context")
    parser.add_argument("--db", default="data/messages.sqlite")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import")
    importer.add_argument("path")
    importer.add_argument("--format", choices=["jsonl", "mbox", "discord-csv"], default="jsonl")
    importer.add_argument("--owner")
    importer.add_argument("--contact")
    importer.add_argument("--thread")
    importer.add_argument("--preview", action="store_true", help="Report validation and duplicates without database writes")
    for name in ("search", "style"):
        sub = commands.add_parser(name)
        sub.add_argument("--owner", required=True)
        sub.add_argument("--contact", required=True)
        sub.add_argument("--before", required=True, help="Exclusive UTC/offset timestamp cutoff")
        sub.add_argument("--limit", type=int, default=5)
        if name == "search":
            sub.add_argument("query")
    args = parser.parse_args()
    if args.command == "import":
        try:
            plan = plan_import(args.path, db=args.db, format=args.format,
                               owner=args.owner, contact=args.contact, thread=args.thread)
        except (OSError, ValueError, sqlite3.Error) as exc:
            parser.exit(2, f"Import inspection failed: {exc}\n")
        result = plan.report | {"preview": args.preview, "inserted": 0}
        if plan.report["ready"] and not args.preview:
            Path(args.db).parent.mkdir(parents=True, exist_ok=True)
            store = Store(args.db)
            try:
                result["inserted"] = store.ingest(plan.messages)
            finally:
                store.close()
        print(json.dumps(result, indent=2))
        if not plan.report["ready"]:
            parser.exit(2)
        return
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    store = Store(args.db)
    try:
        parameters = dict(owner=args.owner, contact=args.contact, before=args.before, limit=args.limit)
        result = store.search(args.query, **parameters) if args.command == "search" else store.style_examples(**parameters)
        print(json.dumps(result, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
