"""SQLite provenance store and a transparent lexical retrieval baseline."""

from collections import Counter
from dataclasses import asdict
import math
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from .messages import Message, utc_timestamp


def tokens(text: str) -> set[str]:
    return set(re.findall(r"\b\w+\b", text.casefold()))


class Store:
    def __init__(self, path: str = ":memory:", *, readonly: bool = False, create: bool = True):
        if readonly or not create:
            mode = 'ro' if readonly else 'rw'
            self.connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode='+mode, uri=True)
            self.connection.row_factory = sqlite3.Row
            if readonly:
                self.connection.execute('PRAGMA query_only = ON')
            return
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("""CREATE TABLE IF NOT EXISTS messages (
            id TEXT NOT NULL, source TEXT NOT NULL, thread TEXT NOT NULL,
            author TEXT NOT NULL, recipient TEXT NOT NULL, timestamp TEXT NOT NULL,
            body TEXT NOT NULL, fingerprint TEXT UNIQUE NOT NULL,
            PRIMARY KEY (source, id))""")
        self.connection.execute("CREATE INDEX IF NOT EXISTS participants_time ON messages(author, recipient, timestamp)")

    def close(self):
        self.connection.close()

    def ingest(self, messages: Iterable[Message]) -> int:
        if self.connection.in_transaction:
            raise ValueError("Finish the pending store transaction before importing messages")
        inserted = 0
        seen = {}
        # One transaction: malformed exports cannot leave a partial import.
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            for message in messages:
                fields = asdict(message) | {"fingerprint": message.fingerprint}
                key = (message.source, message.id)
                previous = seen.get(key)
                if previous is None:
                    existing = self.connection.execute(
                        "SELECT fingerprint FROM messages WHERE source = ? AND id = ?", key).fetchone()
                    previous = existing["fingerprint"] if existing else None
                if previous is not None and previous != fields["fingerprint"]:
                    raise ValueError("Message identifier conflicts with different normalized content; no messages imported")
                seen[key] = fields["fingerprint"]
                result = self.connection.execute("""INSERT INTO messages
                    VALUES (:id, :source, :thread, :author, :recipient, :timestamp, :body, :fingerprint)
                    ON CONFLICT DO NOTHING""", fields)
                inserted += result.rowcount
        return inserted

    def _eligible(self, *, owner: str, contact: str, before: str, style_only: bool) -> list[dict]:
        owner, contact = owner.casefold(), contact.casefold()
        cutoff = utc_timestamp(before)
        if owner == contact:
            raise ValueError("Owner and contact must be different")
        participants = "author = ? AND recipient = ?"
        args = [owner, contact]
        if not style_only:
            participants = f"({participants}) OR (author = ? AND recipient = ?)"
            args += [contact, owner]
        rows = self.connection.execute(f"""SELECT id, source, thread, author, recipient, timestamp, body
            FROM messages WHERE ({participants}) AND timestamp < ? ORDER BY timestamp DESC, source, id""",
            args + [cutoff]).fetchall()
        return [dict(row) for row in rows]

    def search(self, query: str, *, owner: str, contact: str, before: str, limit: int = 5) -> list[dict]:
        if limit < 1:
            raise ValueError("limit must be positive")
        terms = tokens(query)
        if not terms:
            return []
        candidates = self._eligible(owner=owner, contact=contact, before=before, style_only=False)
        documents = [tokens(item["body"]) for item in candidates]
        frequencies = Counter(term for document in documents for term in document)
        results = []
        for item, document in zip(candidates, documents):
            overlap = document & terms
            if overlap:
                score = sum(math.log((1 + len(documents)) / (1 + frequencies[term])) + 1 for term in overlap)
                score /= math.sqrt(max(1, len(document)))
                results.append(item | {"score": round(score, 6)})
        return sorted(results, key=lambda item: (-item["score"], item["timestamp"], item["source"], item["id"]))[:limit]

    def style_examples(self, *, owner: str, contact: str, before: str, limit: int = 5) -> list[dict]:
        if limit < 1:
            raise ValueError("limit must be positive")
        return self._eligible(owner=owner, contact=contact, before=before, style_only=True)[:limit]
