"""Inspect exports and deduplication through read-only database access."""

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .messages import Message, scan_discord_csv, scan_jsonl, scan_mbox


@dataclass
class ImportPlan:
    messages: list[Message]
    report: dict


def _records(path, format, owner, contact, thread):
    if format == "discord-csv":
        if not all((owner, contact, thread)):
            raise ValueError("Discord import requires --owner, --contact, and --thread")
        return scan_discord_csv(path, author=owner, recipient=contact, thread=thread)
    if format == "mbox":
        return scan_mbox(path)
    if format == "jsonl":
        return scan_jsonl(path)
    raise ValueError("Unsupported import format")


def _inspect(records, connection, format):
    ids, fingerprints = {}, set()
    report = dict(format=format, valid=0, invalid=0, skipped=0, duplicates=0, conflicts=0,
                  would_insert=0, errors=[])
    messages = []
    for record in records:
        if record.error:
            report["invalid"] += 1
            report["errors"].append(dict(record=record.number, reason=record.error))
            continue
        if record.skipped:
            report["skipped"] += 1
            continue
        message = record.message
        report["valid"] += 1
        key = (message.source, message.id)
        fingerprint = message.fingerprint
        previous = ids.get(key)
        if previous is None and connection is not None:
            row = connection.execute(
                "SELECT fingerprint FROM messages WHERE source = ? AND id = ?", key).fetchone()
            previous = row[0] if row is not None else None
        if previous is not None and previous != fingerprint:
            report["conflicts"] += 1
            report["errors"].append(dict(record=record.number,
                reason="Message identifier conflicts with different normalized content"))
            continue
        # Reserve aliases even when content deduplicates to an existing record.
        ids[key] = fingerprint
        known_content = fingerprint in fingerprints
        if previous is None and not known_content and connection is not None:
            known_content = connection.execute(
                "SELECT 1 FROM messages WHERE fingerprint = ?", (fingerprint,)).fetchone() is not None
        fingerprints.add(fingerprint)
        if previous is not None or known_content:
            report["duplicates"] += 1
        else:
            messages.append(message)
    report["would_insert"] = len(messages)
    report["ready"] = report["invalid"] == 0 and report["conflicts"] == 0
    return ImportPlan(messages, report)


def _inspect_path(records, db, format):
    if not db.exists():
        return _inspect(records, None, format)
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("BEGIN")
        # Fail consistently even for empty exports against an unsupported store.
        connection.execute("SELECT source, id, fingerprint FROM messages LIMIT 0")
        return _inspect(records, connection, format)


def plan_import(path: str | Path, *, db: str | Path, format: str = "jsonl",
                owner: str | None = None, contact: str | None = None,
                thread: str | None = None) -> ImportPlan:
    """Collect validation and duplicate counts from one read-only store snapshot."""
    return _inspect_path(_records(path, format, owner, contact, thread), Path(db), format)
