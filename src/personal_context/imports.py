"""Inspect exports and deduplication through read-only database access."""

from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
import sqlite3

from .import_staging import stage_records
from .messages import Message, scan_discord_csv, scan_jsonl, scan_mbox
from .store import Store


MAX_REPORTED_ERRORS = 100
ID_CONFLICT = "Message identifier conflicts with different normalized content"


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


def _inspect(staged, connection, format, db):
    snapshot = hashlib.sha256()

    def remember(*fields):
        snapshot.update(json.dumps(fields, separators=(",", ":")).encode("utf-8") + b"\n")

    remember("import-preview-v1", format, str(db))
    staged.reset_plan()
    report = dict(format=format, valid=0, invalid=0, skipped=0, duplicates=0, conflicts=0,
                  would_insert=0, errors=[])

    def add_error(number, reason):
        if len(report["errors"]) < MAX_REPORTED_ERRORS:
            report["errors"].append(dict(record=number, reason=reason))

    for position, record in enumerate(staged.records(), 1):
        if record.error:
            report["invalid"] += 1
            add_error(record.number, record.error)
            continue
        if record.skipped:
            report["skipped"] += 1
            remember(record.number, "skip", record.skipped)
            continue
        message = record.message
        report["valid"] += 1
        key = (message.source, message.id)
        fingerprint = message.fingerprint
        previous = staged.previous_fingerprint(key)
        if previous is None and connection is not None:
            row = connection.execute(
                "SELECT fingerprint FROM messages WHERE source = ? AND id = ?", key).fetchone()
            previous = row[0] if row is not None else None
        if previous is not None and previous != fingerprint:
            report["conflicts"] += 1
            add_error(record.number, ID_CONFLICT)
            continue
        known_content = staged.has_fingerprint(fingerprint)
        if previous is None and not known_content and connection is not None:
            known_content = connection.execute(
                "SELECT 1 FROM messages WHERE fingerprint = ?", (fingerprint,)).fetchone() is not None
        duplicate = previous is not None or known_content
        # Reserve aliases even when content deduplicates to an existing record.
        staged.remember(key, fingerprint, None if duplicate else position)
        if duplicate:
            report["duplicates"] += 1
            remember(record.number, key, fingerprint, "duplicate")
        else:
            report["would_insert"] += 1
            remember(record.number, key, fingerprint, "insert")
    report["errors_omitted"] = report["invalid"] + report["conflicts"] - len(report["errors"])
    report["ready"] = report["invalid"] == 0 and report["conflicts"] == 0
    report["preview_sha256"] = snapshot.hexdigest() if report["ready"] else None
    return report


def _inspect_path(staged, db, format):
    if not db.exists():
        return _inspect(staged, None, format, db)
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("BEGIN")
        # Fail consistently even for empty exports against an unsupported store.
        connection.execute("SELECT source, id, fingerprint FROM messages LIMIT 0")
        return _inspect(staged, connection, format, db)


@contextmanager
def _planned(path, db, format, owner, contact, thread):
    destination = Path(db).resolve()
    with stage_records(_records(path, format, owner, contact, thread)) as staged:
        yield destination, staged, _inspect_path(staged, destination, format)


def plan_import(path: str | Path, *, db: str | Path, format: str = "jsonl",
                owner: str | None = None, contact: str | None = None,
                thread: str | None = None) -> ImportPlan:
    """Return both inspection counts and a materialized list of candidate messages."""
    with _planned(path, db, format, owner, contact, thread) as (_, staged, report):
        return ImportPlan(list(staged.messages()), report)


def preview_import(path: str | Path, *, db: str | Path, format: str = "jsonl",
                   owner: str | None = None, contact: str | None = None,
                   thread: str | None = None) -> dict:
    """Return inspection counts without materializing candidate messages."""
    with _planned(path, db, format, owner, contact, thread) as (_, _, report):
        return report | {"preview": True, "inserted": 0}


def apply_import(path: str | Path, *, db: str | Path, expected_preview: str | None = None,
                 format: str = "jsonl", owner: str | None = None, contact: str | None = None,
                 thread: str | None = None) -> dict:
    """Insert staged candidates atomically, optionally binding them to a preview."""
    if expected_preview is not None and (
            not isinstance(expected_preview, str) or re.fullmatch(r"[0-9a-f]{64}", expected_preview) is None):
        raise ValueError("Expected preview must be a lowercase SHA-256 digest")

    def require_match(report):
        if expected_preview is not None and report["preview_sha256"] != expected_preview:
            raise ValueError("Import preview is stale or blocked; run preview again")

    with _planned(path, db, format, owner, contact, thread) as (destination, staged, report):
        require_match(report)
        if not report["ready"]:
            return report | {"preview": False, "inserted": 0}
        destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(Store(str(destination), create=not destination.exists())) as store:
            with store.connection:
                store.connection.execute("BEGIN IMMEDIATE")
                # Replan from the same parsed records in the writer snapshot.
                report = _inspect(staged, store.connection, format, destination)
                require_match(report)
                if not report["ready"]:
                    raise ValueError(ID_CONFLICT + "; no messages imported")
                inserted = store._insert_planned(staged.messages())
                if inserted != report["would_insert"]:
                    raise ValueError("Database differed from the checked import plan; no messages imported")
    return report | {"preview": False, "inserted": inserted}


def apply_previewed_import(path: str | Path, *, db: str | Path, expected_preview: str,
                           format: str = "jsonl", owner: str | None = None, contact: str | None = None,
                           thread: str | None = None) -> dict:
    """Require the reviewed preview digest before applying an import."""
    if expected_preview is None:
        raise ValueError("Expected preview must be a lowercase SHA-256 digest")
    return apply_import(path, db=db, expected_preview=expected_preview,
                        format=format, owner=owner, contact=contact, thread=thread)
