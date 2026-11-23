"""Disposable local storage for normalized export records."""

from contextlib import closing, contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from .messages import ImportRecord, Message


class StagedRecords:
    def __init__(self, connection, records):
        self.connection = connection
        connection.execute("""CREATE TABLE records (
            position INTEGER PRIMARY KEY, number INTEGER NOT NULL,
            message TEXT, error TEXT, skipped TEXT
        )""")
        connection.executescript("""CREATE TABLE seen_ids (
            source TEXT NOT NULL, message_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
            PRIMARY KEY (source, message_id)
        );
        CREATE INDEX seen_fingerprints ON seen_ids (fingerprint);
        CREATE TABLE candidates (position INTEGER PRIMARY KEY);
        """)
        connection.executemany(
            "INSERT INTO records (number, message, error, skipped) VALUES (?, ?, ?, ?)",
            ((row.number, json.dumps(asdict(row.message)) if row.message is not None else None,
              row.error, row.skipped) for row in records),
        )


    def reset_plan(self):
        self.connection.execute("DELETE FROM seen_ids")
        self.connection.execute("DELETE FROM candidates")

    def previous_fingerprint(self, key):
        row = self.connection.execute(
            "SELECT fingerprint FROM seen_ids WHERE source = ? AND message_id = ?", key).fetchone()
        return row[0] if row is not None else None

    def has_fingerprint(self, fingerprint):
        return self.connection.execute(
            "SELECT 1 FROM seen_ids WHERE fingerprint = ?", (fingerprint,)).fetchone() is not None

    def remember(self, key, fingerprint, candidate_position=None):
        self.connection.execute("INSERT OR IGNORE INTO seen_ids VALUES (?, ?, ?)", (*key, fingerprint))
        if candidate_position is not None:
            self.connection.execute("INSERT INTO candidates VALUES (?)", (candidate_position,))

    def messages(self):
        rows = self.connection.execute("""SELECT records.message FROM candidates
            JOIN records ON records.position = candidates.position ORDER BY candidates.position""")
        return (Message(**json.loads(payload)) for (payload,) in rows)

    def records(self):
        """Replay the same parsed records in export order."""
        rows = self.connection.execute("SELECT number, message, error, skipped FROM records ORDER BY position")
        for number, payload, error, skipped in rows:
            message = Message(**json.loads(payload)) if payload is not None else None
            yield ImportRecord(number, message, error, skipped)


@contextmanager
def stage_records(records):
    """Use a private temporary directory and discard its database on exit."""
    with TemporaryDirectory(prefix="personal-context-import-") as directory:
        with closing(sqlite3.connect(Path(directory)/"stage.sqlite")) as connection:
            connection.execute("PRAGMA cache_size = -2048")
            # The stage has no recovery value. Only the destination needs a journal.
            connection.execute("PRAGMA journal_mode = OFF")
            yield StagedRecords(connection, records)
