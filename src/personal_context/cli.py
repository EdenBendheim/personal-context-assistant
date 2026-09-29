import argparse
import json

from .messages import read_discord_csv, read_jsonl, read_mbox
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
    for name in ("search", "style"):
        sub = commands.add_parser(name)
        sub.add_argument("--owner", required=True)
        sub.add_argument("--contact", required=True)
        sub.add_argument("--before", required=True, help="Exclusive UTC/offset timestamp cutoff")
        sub.add_argument("--limit", type=int, default=5)
        if name == "search":
            sub.add_argument("query")
    args = parser.parse_args()
    from pathlib import Path
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    store = Store(args.db)
    try:
        if args.command == "import":
            if args.format == "discord-csv":
                if not all((args.owner, args.contact, args.thread)):
                    parser.error("Discord import requires --owner, --contact, and --thread")
                messages = read_discord_csv(args.path, author=args.owner, recipient=args.contact, thread=args.thread)
            else:
                messages = read_mbox(args.path) if args.format == "mbox" else read_jsonl(args.path)
            result = {"inserted": store.ingest(messages)}
        else:
            parameters = dict(owner=args.owner, contact=args.contact, before=args.before, limit=args.limit)
            result = store.search(args.query, **parameters) if args.command == "search" else store.style_examples(**parameters)
        print(json.dumps(result, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
