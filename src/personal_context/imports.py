"""Inspect exports and deduplication through read-only database access."""

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .messages import Message, scan_discord_csv, scan_jsonl, scan_mbox


@dataclass
class ImportPlan:
    messages: list[Message]
    report: dict


def plan_import(path: str | Path, *, db: str | Path, format: str = "jsonl",
                owner: str | None = None, contact: str | None = None,
                thread: str | None = None) -> ImportPlan:
    """Collect all validation errors; never create a database or change its bytes.

    Duplicate counts include conflicts within the file and with the existing store.
    Counts are a snapshot, not a promise about concurrent changes before import.
    """
    ids, fingerprints = set(), set()
    db_path = Path(db)
    if db_path.exists():
        connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            for source, id, fingerprint in connection.execute("SELECT source, id, fingerprint FROM messages"):
                ids.add((source, id))
                fingerprints.add(fingerprint)
        finally:
            connection.close()
    if format == "discord-csv":
        if not all((owner, contact, thread)):
            raise ValueError("Discord import requires --owner, --contact, and --thread")
        records = scan_discord_csv(path, author=owner, recipient=contact, thread=thread)
    elif format == "mbox":
        records = scan_mbox(path)
    elif format == "jsonl":
        records = scan_jsonl(path)
    else:
        raise ValueError("Unsupported import format")
    report = dict(format=format, valid=0, invalid=0, skipped=0, duplicates=0,
                  would_insert=0, errors=[])
    messages = []
    for record in records:
        if record.error:
            report["invalid"] += 1
            report["errors"].append(dict(record=record.number, reason=record.error))
        elif record.skipped:
            report["skipped"] += 1
        else:
            message = record.message
            report["valid"] += 1
            key = (message.source, message.id)
            fingerprint = message.fingerprint
            if key in ids or fingerprint in fingerprints:
                report["duplicates"] += 1
            else:
                ids.add(key)
                fingerprints.add(fingerprint)
                messages.append(message)
    report["would_insert"] = len(messages)
    report["ready"] = report["invalid"] == 0
    return ImportPlan(messages, report)
