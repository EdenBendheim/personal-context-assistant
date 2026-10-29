"""Owner-scoped memory inspection with current supporting-message snapshots."""

from dataclasses import asdict
from contextlib import contextmanager

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

    @contextmanager
    def _inspection(self):
        # Keep source status and revisions in one read snapshot; never commit caller writes.
        connection = self.store.connection
        own = not connection.in_transaction
        if own:
            connection.execute('BEGIN')
        try:
            yield
        finally:
            if own:
                connection.rollback()

    def _contact(self, memory_id: str) -> str:
        row = self.store.connection.execute("SELECT contact FROM memory_items WHERE id = ? AND owner = ?",
                                            (memory_id, self.owner)).fetchone()
        if row is None:
            raise ValueError("Memory does not exist for this owner")
        return row['contact']

    def _read(self, memory_id: str, *, include_history=True) -> dict:
        contact = self._contact(memory_id)
        if include_history:
            history = self.memory.history(memory_id)
        else:
            row = self.store.connection.execute('''SELECT i.owner, i.contact, i.kind, r.*
                FROM memory_items i JOIN memory_revisions r ON r.memory_id = i.id
                WHERE i.id = ? ORDER BY r.revision DESC LIMIT 1''', (memory_id,)).fetchone()
            history = [self.memory._snapshot(row)]
        self._source_messages(history, contact)
        return dict(history[-1], history=history) if include_history else history[-1]

    def _source_messages(self, history, contact):
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

    def _eligible(self, request: DraftRequest, memory_ids=None) -> dict[str, int]:
        if memory_ids == []:
            return {}
        count = len(memory_ids) if memory_ids is not None else self.store.connection.execute(
            'SELECT COUNT(*) FROM memory_items WHERE owner = ? AND contact = ?',
            (self.owner, request.contact)).fetchone()[0]
        return {item["memory_id"]:item["revision"] for item in self.memory.context(
            owner=self.owner, contact=request.contact, before=request.before,
            limit=max(1, count), memory_ids=memory_ids)}

    def get(self, memory_id: str, *, before: str | None = None, include_history: bool = True) -> dict:
        if type(include_history) is not bool:
            raise ValueError('include_history must be boolean')
        with self._inspection():
            item = self._read(memory_id, include_history=include_history)
            request = DraftRequest(self.owner, item["contact"], before if before is not None else now(), "inspect")
            eligible = self._eligible(request, [memory_id])
            return dict(item, eligible_at_cutoff=memory_id in eligible, context_revision=eligible.get(memory_id))

    def page(self, *, contact: str, before: str, limit: int = 25, cursor: str | None = None) -> dict:
        """Current summaries ordered by immutable creation time, not latest edit time."""
        request = DraftRequest(self.owner, contact, before, 'list')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Page limit must be an integer between 1 and 100')
        with self._inspection():
            parameters = [self.owner, request.contact]
            boundary = ''
            if cursor is not None:
                cursor = nonempty(cursor, 'Memory cursor')
                anchor = self.store.connection.execute('''SELECT i.id, r.effective_at FROM memory_items i
                    JOIN memory_revisions r ON r.memory_id = i.id AND r.revision = 1
                    WHERE i.owner = ? AND i.contact = ? AND i.id = ?''', (*parameters, cursor)).fetchone()
                if anchor is None:
                    raise ValueError('Memory cursor is unavailable for this conversation; reload the list')
                boundary = 'AND (r.effective_at < ? OR (r.effective_at = ? AND i.id < ?))'
                parameters += [anchor['effective_at'], anchor['effective_at'], anchor['id']]
            rows = self.store.connection.execute(f'''SELECT i.id, r.effective_at AS created_at
                FROM memory_items i JOIN memory_revisions r ON r.memory_id = i.id AND r.revision = 1
                WHERE i.owner = ? AND i.contact = ? {boundary}
                ORDER BY r.effective_at DESC, i.id DESC LIMIT ?''', (*parameters, limit+1)).fetchall()
            eligible = self._eligible(request, [row['id'] for row in rows[:limit]])
            items = [dict(self._read(row['id'], include_history=False), created_at=row['created_at'],
                          eligible_at_cutoff=row['id'] in eligible, context_revision=eligible.get(row['id']))
                     for row in rows[:limit]]
            return dict(items=items, next_cursor=items[-1]['memory_id'] if len(rows) > limit else None)

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
