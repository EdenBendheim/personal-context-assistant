"""Preview contact data removal, including saved packets and revision copies.

This operates on the current SQLite store. It cannot find external exports,
backups, copied text, provider logs, filesystem snapshots, or flash remnants.
"""
from contextlib import contextmanager
import hashlib
import json

from .memory import scope
from .store import Store

TABLES = {
    'messages': ('id', 'source', 'thread', 'author', 'recipient', 'timestamp', 'body', 'fingerprint'),
    'memory_items': ('id', 'owner', 'contact', 'kind'),
    'memory_revisions': ('memory_id', 'revision', 'text', 'status', 'effective_at', 'reason'),
    'memory_sources': ('memory_id', 'revision', 'source', 'message_id', 'fingerprint'),
    'draft_reviews': ('id', 'owner', 'contact', 'created_at', 'result_json'),
    'draft_edits': ('review_id', 'revision', 'text', 'saved_at'),
    'draft_feedback': ('id', 'review_id', 'revision', 'decision', 'retrieval', 'style', 'notes', 'recorded_at', 'support'),
}
LIMITATIONS = (
    'Current SQLite store only; external exports, backups, browser displays, copied text and provider logs are not removed. '
    'Uncited text copies in other conversations are not detected. No guarantee of physical storage erasure. '
    'Reimporting an original export can restore deleted data.'
)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class Privacy:
    def __init__(self, store: Store):
        self.connection = store.connection

    @contextmanager
    def _transaction(self, *, write=False):
        if self.connection.in_transaction:
            raise ValueError('Finish the pending store transaction before inspecting privacy changes')
        self.connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def _snapshot(self):
        schema = [dict(row) for row in self.connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]
        names = {row['name'] for row in schema if row['type'] == 'table'}
        if ('messages' not in names or names - TABLES.keys()
                or any(row['type'] not in ('table', 'index') for row in schema)):
            raise ValueError('Unsupported database schema; cannot account for all stored copies')
        for group in ({'memory_items', 'memory_revisions', 'memory_sources'},
                      {'draft_reviews', 'draft_edits', 'draft_feedback'}):
            if names & group and not group <= names:
                raise ValueError('Incomplete application schema; cannot account for stored copies')
        rows = {}
        for table in sorted(names):
            columns = tuple(row['name'] for row in self.connection.execute(f'PRAGMA table_info({table})'))
            allowed = TABLES[table]
            # Historical feedback rows predate the optional support-review field.
            if columns != allowed and not (table == 'draft_feedback' and columns == allowed[:-1]):
                raise ValueError('Unsupported database columns; cannot account for stored copies')
            rows[table] = [dict(row) for row in self.connection.execute(
                f'SELECT * FROM {table} ORDER BY '+','.join(columns))]
        if self.connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError('Database has broken source relationships; resolve them before removal')
        return dict(schema=schema, rows=rows)

    @staticmethod
    def _references(value, message_keys, memory_ids, pair, depth=0):
        if depth > 64:
            raise ValueError('Saved packet nesting exceeds the privacy inspection bound')
        if isinstance(value, dict):
            refs = ((value.get('source'), value.get('id')), (value.get('source'), value.get('message_id')))
            if (any(all(isinstance(v, str) for v in ref) and ref in message_keys for ref in refs)
                    or (isinstance(value.get('memory_id'), str) and value['memory_id'] in memory_ids)
                    or ((value.get('author'), value.get('recipient')) in (pair, pair[::-1]))):
                return True
            return any(Privacy._references(child, message_keys, memory_ids, pair, depth+1) for child in value.values())
        if isinstance(value, list):
            return any(Privacy._references(child, message_keys, memory_ids, pair, depth+1) for child in value)
        return False

    def _plan(self, snapshot, owner, contact):
        owner, contact = scope(owner, contact)
        pair = (owner, contact)
        rows = snapshot['rows']
        messages = {(row['source'], row['id']) for row in rows['messages']
                    if (row['author'], row['recipient']) in (pair, pair[::-1])}
        memories = {row['id'] for row in rows.get('memory_items', []) if (row['owner'], row['contact']) == pair}
        reviews = {row['id'] for row in rows.get('draft_reviews', []) if (row['owner'], row['contact']) == pair}
        selected = {}
        for table, records in rows.items():
            if table == 'messages':
                wanted = lambda row: (row['source'], row['id']) in messages
            elif table == 'memory_items':
                wanted = lambda row: row['id'] in memories
            elif table.startswith('memory_'):
                wanted = lambda row: row['memory_id'] in memories
            elif table == 'draft_reviews':
                wanted = lambda row: row['id'] in reviews
            else:
                wanted = lambda row: row['review_id'] in reviews
            selected[table] = [row for row in records if wanted(row)]
        blockers = dict(memory_sources_outside_scope=0, saved_reviews_outside_scope=0,
                        reverse_owner_memory=0)
        for row in rows.get('memory_sources', []):
            if row['memory_id'] not in memories and (row['source'], row['message_id']) in messages:
                blockers['memory_sources_outside_scope'] += 1
        blockers['reverse_owner_memory'] = sum((row['owner'], row['contact']) == pair[::-1]
                                               for row in rows.get('memory_items', []))
        for row in rows.get('draft_reviews', []):
            if row['id'] in reviews:
                continue
            try:
                packet = json.loads(row['result_json'])
            except (ValueError, TypeError, RecursionError):
                raise ValueError('A saved packet cannot be inspected for retained source copies') from None
            if ((row['owner'], row['contact']) == pair[::-1]
                    or self._references(packet, messages, memories, pair)):
                blockers['saved_reviews_outside_scope'] += 1
        document = dict(version=1, owner=owner, contact=contact,
            store_sha256=_hash(snapshot), counts={table: len(selected.get(table, [])) for table in TABLES},
            blockers=blockers, can_apply=not any(blockers.values()), limitation=LIMITATIONS)
        return document | dict(plan_sha256=_hash(document)), selected

    def preview(self, *, owner, contact):
        """Read a consistent snapshot, exposing counts/hashes rather than message text."""
        with self._transaction():
            plan, _ = self._plan(self._snapshot(), owner, contact)
        return plan

    def _delete_rows(self, selected):
        # Children first: this also works when SQLite foreign-key checks are on.
        keys = dict(messages=('source', 'id'), memory_items=('id',),
            memory_revisions=('memory_id', 'revision'),
            memory_sources=('memory_id', 'revision', 'source', 'message_id'),
            draft_reviews=('id',), draft_edits=('review_id', 'revision'), draft_feedback=('id',))
        for table in ('draft_feedback', 'draft_edits', 'draft_reviews',
                      'memory_sources', 'memory_revisions', 'memory_items', 'messages'):
            rows = selected.get(table, [])
            if rows:
                columns = keys[table]
                cursor = self.connection.executemany(
                    f'DELETE FROM {table} WHERE '+' AND '.join(f'{column} = ?' for column in columns),
                    [tuple(row[column] for column in columns) for row in rows])
                if cursor.rowcount != len(rows):
                    raise ValueError('Removal count differs from the reviewed plan')

    def apply(self, *, owner, contact, expected_plan_sha256, confirm=False):
        """Remove exactly the reviewed scope; changed state requires a new preview.

        ``confirm=True`` is an explicit caller decision, never inferred from a
        preview. The transaction removes current live records, not external copies.
        """
        if confirm is not True:
            raise ValueError('Explicit confirmation is required to remove stored contact data')
        if (not isinstance(expected_plan_sha256, str) or len(expected_plan_sha256) != 64
                or any(c not in '0123456789abcdef' for c in expected_plan_sha256)):
            raise ValueError('Supply the exact preview plan SHA-256')
        if self.connection.in_transaction:
            raise ValueError('Finish the pending store transaction before removing contact data')
        previous_secure = self.connection.execute('PRAGMA secure_delete').fetchone()[0]
        try:
            self.connection.execute('PRAGMA secure_delete = ON')
            with self._transaction(write=True):
                snapshot = self._snapshot()
                plan, selected = self._plan(snapshot, owner, contact)
                if plan['plan_sha256'] != expected_plan_sha256:
                    raise ValueError('Stale removal plan; preview the current store before confirming again')
                if not plan['can_apply']:
                    raise ValueError('Other scopes retain source copies; resolve their ownership before removal')
                self._delete_rows(selected)
                after = self._snapshot()
                expected = dict(schema=snapshot['schema'], rows={table: [row for row in records
                    if row not in selected[table]] for table, records in snapshot['rows'].items()})
                if after != expected:
                    raise ValueError('Removal changed records outside the reviewed scope')
                return dict(version=1, owner=plan['owner'], contact=plan['contact'],
                    applied_plan_sha256=plan['plan_sha256'], deleted=plan['counts'],
                    remaining_counts={table: len(rows) for table, rows in after['rows'].items()},
                    store_sha256=_hash(after), secure_delete_enabled=True,
                    physical_erasure_guaranteed=False, limitation=LIMITATIONS)
        finally:
            self.connection.execute(f'PRAGMA secure_delete = {int(previous_secure)}')
