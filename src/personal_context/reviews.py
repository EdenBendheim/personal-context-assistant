"""Persistent, owner-scoped draft review and immutable edit history."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import uuid

from .drafts import DraftEngine, DraftRequest
from .memory import nonempty
from .store import Store


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def revision_number(value):
    if type(value) is not int or value < 1:
        raise ValueError("Expected revision must be a positive integer")


class Reviews:
    def __init__(self, store: Store):
        self.store = store
        self.connection = store.connection
        self.engine = DraftEngine(store)
        with self.connection:
            self.connection.execute("""CREATE TABLE IF NOT EXISTS draft_reviews (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, contact TEXT NOT NULL,
                created_at TEXT NOT NULL, result_json TEXT NOT NULL)""")
            self.connection.execute("""CREATE TABLE IF NOT EXISTS draft_edits (
                review_id TEXT NOT NULL REFERENCES draft_reviews(id), revision INTEGER NOT NULL,
                text TEXT NOT NULL, saved_at TEXT NOT NULL, PRIMARY KEY(review_id, revision))""")
            self.connection.execute("CREATE INDEX IF NOT EXISTS draft_scope ON draft_reviews(owner, contact)")

    @contextmanager
    def _write(self):
        if self.connection.in_transaction:
            raise ValueError("Finish the pending store transaction before editing a review")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def _row(self, review_id: str, owner: str):
        row = self.connection.execute("SELECT * FROM draft_reviews WHERE id = ? AND owner = ?",
                                      (review_id, nonempty(owner, "Owner").casefold())).fetchone()
        if row is None:
            raise ValueError("Review does not exist for this owner")
        return row

    def create(self, request: DraftRequest) -> dict:
        with self._write():
            result = self.engine.draft(request)
            if result["status"] != "needs_review":
                return result
            review_id, created = str(uuid.uuid4()), now()
            self.connection.execute("INSERT INTO draft_reviews VALUES (?, ?, ?, ?, ?)",
                                    (review_id, request.owner, request.contact, created, json.dumps(result)))
            self.connection.execute("INSERT INTO draft_edits VALUES (?, 1, ?, ?)",
                                    (review_id, result["draft_text"], created))
            return self.get(review_id, owner=request.owner)

    def get(self, review_id: str, *, owner: str) -> dict:
        row = self._row(review_id, owner)
        result = json.loads(row["result_json"])
        edit = self.connection.execute("SELECT * FROM draft_edits WHERE review_id = ? ORDER BY revision DESC LIMIT 1",
                                       (review_id,)).fetchone()
        request = DraftRequest(**result["packet"]["request"])
        current = self.engine.prepare(request).fingerprint == result["packet_sha256"]
        return dict(review_id=review_id, owner=row["owner"], contact=row["contact"],
                    created_at=row["created_at"], revision=edit["revision"], text=edit["text"],
                    saved_at=edit["saved_at"], context_current=current, original=result)

    def edit(self, review_id: str, *, owner: str, expected_revision: int, text: str) -> dict:
        revision_number(expected_revision)
        nonempty(text, "Draft text")
        if len(text) > 100_000:
            raise ValueError("Draft text exceeds 100,000 characters")
        with self._write():
            current = self.get(review_id, owner=owner)
            if current["revision"] != expected_revision:
                raise ValueError("Stale review revision; reload before editing")
            if current["text"] == text:
                return current
            self.connection.execute("INSERT INTO draft_edits VALUES (?, ?, ?, ?)",
                                    (review_id, expected_revision+1, text, now()))
            return self.get(review_id, owner=owner)

    def history(self, review_id: str, *, owner: str) -> list[dict]:
        self._row(review_id, owner)
        return [dict(row) for row in self.connection.execute(
            "SELECT revision, text, saved_at FROM draft_edits WHERE review_id = ? ORDER BY revision", (review_id,))]

    def list(self, *, owner: str, contact: str) -> list[dict]:
        request = DraftRequest(owner, contact, now(), "list")
        rows = self.connection.execute("""SELECT id, created_at FROM draft_reviews WHERE owner = ? AND contact = ?
            ORDER BY created_at DESC, id LIMIT 100""", (request.owner, request.contact))
        return [dict(review_id=row["id"], created_at=row["created_at"]) for row in rows]
