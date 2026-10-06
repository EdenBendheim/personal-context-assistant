"""Build a local draft review packet; never send a message."""

import argparse
import json
from pathlib import Path
import sqlite3

from .drafts import DraftEngine, DraftRequest
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Inspect a cited extractive draft and its recipient context")
    parser.add_argument("--db", type=Path, required=True, help="Existing imported local message database")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--contact", required=True)
    parser.add_argument("--before", required=True, help="Exclusive timezone-aware context cutoff")
    parser.add_argument("--query", required=True, help="Reply topic and lexical retrieval query")
    parser.add_argument("--mode", choices=("generic", "context", "personalized"), default="personalized")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error("Import messages into an existing database first")
    store = Store(str(args.db))
    try:
        request = DraftRequest(args.owner, args.contact, args.before, args.query, args.mode, args.limit)
        print(json.dumps(DraftEngine(store).draft(request), indent=2))
    except (ValueError, sqlite3.Error) as exc:
        parser.error(str(exc))
    finally:
        store.close()


if __name__ == "__main__":
    main()
