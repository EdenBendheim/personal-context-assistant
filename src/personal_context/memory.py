"""Human-reviewed, contact-scoped memory with immutable cited revisions."""

from contextlib import contextmanager
from datetime import datetime, timezone
import uuid

from .messages import Message, utc_timestamp
from .store import Store


def nonempty(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value.strip()


def scope(owner: str, contact: str) -> tuple[str, str]:
    pair = (nonempty(owner, "Owner").casefold(), nonempty(contact, "Contact").casefold())
    if pair[0] == pair[1]:
        raise ValueError("Owner and contact must be different")
    return pair


class Memory:
    def __init__(self, store: Store):
        self.connection = store.connection
        if self.connection.in_transaction:
            raise ValueError("Finish the pending store transaction before opening memory")
        self.connection.execute("PRAGMA foreign_keys = ON")
        with self.connection:
            self.connection.execute("""CREATE TABLE IF NOT EXISTS memory_items (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, contact TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('fact', 'preference')))""")
            self.connection.execute("""CREATE TABLE IF NOT EXISTS memory_revisions (
                memory_id TEXT NOT NULL REFERENCES memory_items(id), revision INTEGER NOT NULL,
                text TEXT, status TEXT NOT NULL CHECK(status IN ('active', 'revoked')),
                effective_at TEXT NOT NULL, reason TEXT NOT NULL,
                PRIMARY KEY(memory_id, revision),
                CHECK(revision > 0),
                CHECK((status = 'active' AND text IS NOT NULL) OR (status = 'revoked' AND text IS NULL)))""")
            # Source references intentionally survive removal of raw messages for auditing.
            self.connection.execute("""CREATE TABLE IF NOT EXISTS memory_sources (
                memory_id TEXT NOT NULL, revision INTEGER NOT NULL,
                source TEXT NOT NULL, message_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                PRIMARY KEY(memory_id, revision, source, message_id),
                FOREIGN KEY(memory_id, revision) REFERENCES memory_revisions(memory_id, revision))""")
            self.connection.execute("CREATE INDEX IF NOT EXISTS memory_scope ON memory_items(owner, contact)")

    @contextmanager
    def _write(self):
        if self.connection.in_transaction:
            raise ValueError("Finish the pending store transaction before editing memory")
        # Serialize revision checks and writes across connections; stale editors fail cleanly.
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def _message(self, source: str, message_id: str) -> Message | None:
        row = self.connection.execute("""SELECT id, source, thread, author, recipient, timestamp, body
            FROM messages WHERE source = ? AND id = ?""", (source, message_id)).fetchone()
        return Message(**dict(row)) if row else None

    def _sources(self, refs, *, owner: str, contact: str, at: str) -> list[dict]:
        if not isinstance(refs, (list, tuple)) or not refs:
            raise ValueError("Active memory requires at least one source/message pair")
        result, seen = [], set()
        for ref in refs:
            if not isinstance(ref, (list, tuple)) or len(ref) != 2:
                raise ValueError("Each source must be a source/message pair")
            source, message_id = (nonempty(value, "Source reference") for value in ref)
            if (source, message_id) in seen:
                raise ValueError("Duplicate source/message pair")
            seen.add((source, message_id))
            message = self._message(source, message_id)
            if message is None:
                raise ValueError("Supporting message does not exist")
            if (message.author, message.recipient) not in ((owner, contact), (contact, owner)):
                raise ValueError("Supporting message belongs to another contact")
            if message.timestamp > at:
                raise ValueError("Supporting message is later than the memory revision")
            result.append(dict(source=source, message_id=message_id, fingerprint=message.fingerprint))
        return result

    def _append(self, memory_id: str, revision: int, *, text: str | None, status: str,
                at: str, reason: str, sources: list[dict]):
        self.connection.execute("INSERT INTO memory_revisions VALUES (?, ?, ?, ?, ?, ?)",
                                (memory_id, revision, text, status, at, reason))
        self.connection.executemany("INSERT INTO memory_sources VALUES (?, ?, ?, ?, ?)",
                                    [(memory_id, revision, ref["source"], ref["message_id"], ref["fingerprint"])
                                     for ref in sources])

    @staticmethod
    def _at(value: str | None) -> str:
        return utc_timestamp(value if value is not None else datetime.now(timezone.utc).isoformat())

    def create(self, *, owner: str, contact: str, kind: str, text: str,
               sources, reason: str, at: str | None = None) -> dict:
        owner, contact = scope(owner, contact)
        if kind not in ("fact", "preference"):
            raise ValueError("Memory kind must be fact or preference")
        text, reason, timestamp = nonempty(text, "Text"), nonempty(reason, "Reason"), self._at(at)
        memory_id = str(uuid.uuid4())
        with self._write():
            refs = self._sources(sources, owner=owner, contact=contact, at=timestamp)
            self.connection.execute("INSERT INTO memory_items VALUES (?, ?, ?, ?)", (memory_id, owner, contact, kind))
            self._append(memory_id, 1, text=text, status="active", at=timestamp, reason=reason, sources=refs)
            result = self.history(memory_id)[-1]
        return result

    def _current(self, memory_id: str, expected_revision: int, at: str) -> dict:
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("Expected revision must be a positive integer")
        row = self.connection.execute("""SELECT i.*, r.* FROM memory_items i JOIN memory_revisions r
            ON i.id = r.memory_id WHERE i.id = ? ORDER BY revision DESC LIMIT 1""", (memory_id,)).fetchone()
        if row is None:
            raise ValueError("Memory does not exist")
        current = dict(row)
        if current["revision"] != expected_revision:
            raise ValueError("Stale revision; review the current memory before editing")
        if current["status"] == "revoked":
            raise ValueError("Revoked memory cannot be edited; create a new reviewed item")
        if at <= current["effective_at"]:
            raise ValueError("Revision timestamps must increase strictly")
        return current

    def revise(self, memory_id: str, *, expected_revision: int, text: str, sources,
               reason: str, at: str | None = None) -> dict:
        text, reason, timestamp = nonempty(text, "Text"), nonempty(reason, "Reason"), self._at(at)
        with self._write():
            current = self._current(memory_id, expected_revision, timestamp)
            refs = self._sources(sources, owner=current["owner"], contact=current["contact"], at=timestamp)
            self._append(memory_id, expected_revision+1, text=text, status="active", at=timestamp,
                         reason=reason, sources=refs)
            result = self.history(memory_id)[-1]
        return result

    def revoke(self, memory_id: str, *, expected_revision: int, reason: str, at: str | None = None) -> dict:
        reason, timestamp = nonempty(reason, "Reason"), self._at(at)
        with self._write():
            self._current(memory_id, expected_revision, timestamp)
            self._append(memory_id, expected_revision+1, text=None, status="revoked", at=timestamp,
                         reason=reason, sources=[])
            result = self.history(memory_id)[-1]
        return result

    def _snapshot(self, row) -> dict:
        result = dict(row)
        result["sources"] = [dict(ref) for ref in self.connection.execute("""SELECT source, message_id, fingerprint
            FROM memory_sources WHERE memory_id = ? AND revision = ? ORDER BY source, message_id""",
            (result["memory_id"], result["revision"]))]
        return result

    def history(self, memory_id: str) -> list[dict]:
        rows = self.connection.execute("""SELECT i.owner, i.contact, i.kind, r.* FROM memory_items i
            JOIN memory_revisions r ON i.id = r.memory_id WHERE i.id = ? ORDER BY revision""", (memory_id,)).fetchall()
        if not rows:
            raise ValueError("Memory does not exist")
        return [self._snapshot(row) for row in rows]

    def context(self, *, owner: str, contact: str, before: str, limit: int = 10) -> list[dict]:
        owner, contact = scope(owner, contact)
        cutoff = utc_timestamp(before)
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        rows = self.connection.execute("""SELECT i.owner, i.contact, i.kind, r.* FROM memory_items i
            JOIN memory_revisions r ON i.id = r.memory_id WHERE i.owner = ? AND i.contact = ?
            AND r.revision = (SELECT MAX(v.revision) FROM memory_revisions v
                             WHERE v.memory_id = i.id AND v.effective_at < ?)
            AND (SELECT v.status FROM memory_revisions v WHERE v.memory_id = i.id
                 ORDER BY v.revision DESC LIMIT 1) = 'active'
            ORDER BY r.effective_at DESC, i.id""", (owner, contact, cutoff)).fetchall()
        results = []
        for row in rows:
            item = self._snapshot(row)
            valid = bool(item["sources"])
            for ref in item["sources"]:
                message = self._message(ref["source"], ref["message_id"])
                if (message is None or message.fingerprint != ref["fingerprint"]
                        or (message.author, message.recipient) not in ((owner, contact), (contact, owner))
                        or message.timestamp >= cutoff):
                    valid = False
                    break
            if valid:
                results.append(item)
                if len(results) == limit:
                    break
        return results
