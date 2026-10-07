"""Owner-scoped memory inspection with current supporting-message snapshots."""

from dataclasses import asdict

from .drafts import DraftRequest
from .memory import Memory, nonempty
from .messages import Message
from .reviews import now
from .store import Store


class MemoryWorkspace:
    def __init__(self, store: Store, *, owner: str):
        self.store = store
        self.owner = nonempty(owner, "Owner").casefold()
        self.memory = Memory(store)

    def _read(self, memory_id: str) -> dict:
        row = self.store.connection.execute("SELECT contact FROM memory_items WHERE id = ? AND owner = ?",
                                            (memory_id, self.owner)).fetchone()
        if row is None:
            raise ValueError("Memory does not exist for this owner")
        contact = row["contact"]
        history = self.memory.history(memory_id)
        for item in history:
            item["source_messages"] = []
            for ref in item["sources"]:
                source = self.store.connection.execute("""SELECT id, source, thread, author, recipient, timestamp, body
                    FROM messages WHERE source = ? AND id = ?""", (ref["source"], ref["message_id"])).fetchone()
                message = Message(**dict(source)) if source else None
                pair = (self.owner, contact)
                # Never expose a message moved into another participant pair, even through an old citation.
                in_scope = message is not None and (message.author, message.recipient) in (pair, pair[::-1])
                item["source_messages"].append(dict(source=ref["source"], message_id=ref["message_id"],
                    current=bool(in_scope and message.fingerprint == ref["fingerprint"]),
                    message=asdict(message) if in_scope else None))
        return dict(history[-1], history=history)

    def _eligible(self, request: DraftRequest) -> dict[str, int]:
        count = self.store.connection.execute("SELECT COUNT(*) FROM memory_items WHERE owner = ? AND contact = ?",
                                             (self.owner, request.contact)).fetchone()[0]
        return {item["memory_id"]:item["revision"] for item in self.memory.context(
            owner=self.owner, contact=request.contact, before=request.before, limit=max(1, count))}

    def get(self, memory_id: str, *, before: str | None = None) -> dict:
        item = self._read(memory_id)
        request = DraftRequest(self.owner, item["contact"], before if before is not None else now(), "inspect")
        eligible = self._eligible(request)
        return dict(item, eligible_at_cutoff=memory_id in eligible, context_revision=eligible.get(memory_id))

    def list(self, *, contact: str, before: str) -> list[dict]:
        request = DraftRequest(self.owner, contact, before, "list")
        ids = self.store.connection.execute("""SELECT i.id FROM memory_items i
            JOIN memory_revisions r ON r.memory_id = i.id
            AND r.revision = (SELECT MAX(revision) FROM memory_revisions WHERE memory_id = i.id)
            WHERE i.owner = ? AND i.contact = ? ORDER BY r.effective_at DESC, i.id LIMIT 100""",
            (self.owner, request.contact)).fetchall()
        eligible = self._eligible(request)
        return [dict(self._read(row["id"]), eligible_at_cutoff=row["id"] in eligible,
                     context_revision=eligible.get(row["id"])) for row in ids]

    def create(self, *, contact: str, kind: str, text: str, sources, reason: str) -> dict:
        item = self.memory.create(owner=self.owner, contact=contact, kind=kind, text=text, sources=sources, reason=reason)
        return self.get(item["memory_id"])

    def revise(self, memory_id: str, **kwargs) -> dict:
        self.get(memory_id)  # Owner check before any write; memory scope is immutable.
        self.memory.revise(memory_id, **kwargs)
        return self.get(memory_id)

    def withdraw(self, memory_id: str, *, expected_revision: int, reason: str) -> dict:
        self.get(memory_id)
        self.memory.revoke(memory_id, expected_revision=expected_revision, reason=reason)
        return self.get(memory_id)
