import argparse
import json
from pathlib import Path
import sqlite3

from .imports import apply_import, preview_import
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
    mode = importer.add_mutually_exclusive_group()
    mode.add_argument("--preview", action="store_true", help="Report validation and duplicates without database writes")
    mode.add_argument("--expect-preview", metavar="SHA256", help="Apply only if the reviewed import plan still matches")
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
        options = dict(db=args.db, format=args.format, owner=args.owner,
                       contact=args.contact, thread=args.thread)
        try:
            result = (preview_import(args.path, **options) if args.preview else
                      apply_import(args.path, expected_preview=args.expect_preview, **options))
        except ValueError as exc:
            parser.exit(2, f"Import failed: {exc}\n")
        except (OSError, sqlite3.Error):
            parser.exit(2, "Unable to inspect or import the local export; no messages were inserted\n")
        print(json.dumps(result, indent=2))
        if not result["ready"]:
            parser.exit(2)
        return
    store = None
    try:
        if not Path(args.db).is_file():
            raise ValueError("Import messages into an existing database before searching")
        store = Store(args.db, readonly=True)
        parameters = dict(owner=args.owner, contact=args.contact, before=args.before, limit=args.limit)
        result = store.search(args.query, **parameters) if args.command == "search" else store.style_examples(**parameters)
        print(json.dumps(result, indent=2))
    except ValueError as exc:
        parser.exit(2, f"Context lookup failed: {exc}\n")
    except (OSError, sqlite3.Error):
        parser.exit(2, "Context lookup failed; use an existing supported database\n")
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    main()
