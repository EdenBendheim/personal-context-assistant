from pathlib import Path
import json
import tempfile
import unittest

from personal_context.drafts import DraftRequest
from personal_context.memory import Memory
from personal_context.messages import Message
from personal_context.privacy import Privacy
from personal_context.reviews import Reviews
from personal_context.store import Store

OWNER, CONTACT, OTHER = 'owner@example.invalid', 'alex@example.invalid', 'riley@example.invalid'


def seed(store):
    store.ingest([Message.from_dict(dict(id=str(i), source='synthetic', thread='demo', author=OWNER,
        recipient=contact, timestamp='2026-09-01T10:00:00Z', body='demo secret-'+contact))
        for i, contact in enumerate((CONTACT, OTHER), 1)])
    memory = Memory(store)
    item = memory.create(owner=OWNER, contact=CONTACT, kind='fact', text='private memory',
                         sources=[('synthetic', '1')], reason='private reason', at='2026-09-02T00:00:00Z')
    memory.revise(item['memory_id'], expected_revision=1, text='corrected memory', sources=[('synthetic', '1')],
                  reason='correction reason', at='2026-09-03T00:00:00Z')
    reviews = Reviews(store)
    review = reviews.create(DraftRequest(OWNER, CONTACT, '2026-09-04T00:00:00Z', 'demo'))
    reviews.edit(review['review_id'], owner=OWNER, expected_revision=1, text='private edited wording')
    reviews.feedback(review['review_id'], owner=OWNER, expected_revision=2, decision='needs_work', notes='private feedback')
    reviews.create(DraftRequest(OWNER, OTHER, '2026-09-04T00:00:00Z', 'demo'))
    return item, review


class PrivacyTests(unittest.TestCase):
    def test_readonly_preview_counts_all_copies_without_mutations_or_body_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'test.sqlite'
            store = Store(str(path)); seed(store); store.close()
            before = path.read_bytes()
            store = Store(str(path), readonly=True)
            try:
                plan = Privacy(store).preview(owner=OWNER.upper(), contact=CONTACT.upper())
                self.assertEqual(plan, Privacy(store).preview(owner=OWNER, contact=CONTACT))
                self.assertEqual(dict(messages=1, memory_items=1, memory_revisions=2, memory_sources=2,
                                      draft_reviews=1, draft_edits=2, draft_feedback=1), plan['counts'])
                self.assertTrue(plan['can_apply'])
                self.assertNotIn('private', json.dumps(plan))
                self.assertNotIn('secret-', json.dumps(plan))
                self.assertEqual(before, path.read_bytes())
                self.assertFalse(store.connection.in_transaction)
            finally: store.close()

    def test_outside_copies_and_reverse_owner_data_block_without_exposing_them(self):
        store = Store(); self.addCleanup(store.close)
        _, review = seed(store)
        reviews = Reviews(store)
        reverse = reviews.create(DraftRequest(CONTACT, OWNER, '2026-09-04T00:00:00Z', 'demo'))
        plan = Privacy(store).preview(owner=OWNER, contact=CONTACT)
        self.assertEqual(1, plan['blockers']['saved_reviews_outside_scope'])
        self.assertFalse(plan['can_apply'])
        # A moved message can leave an earlier snapshot in another scope.
        with store.connection:
            store.connection.execute('UPDATE draft_reviews SET contact=? WHERE id=?', (OTHER, reverse['review_id']))
        self.assertFalse(Privacy(store).preview(owner=OWNER, contact=CONTACT)['can_apply'])
        self.assertNotIn(reverse['review_id'], json.dumps(plan))

    def test_minimal_schema_noop_and_pending_or_unknown_schema_fail_closed(self):
        store = Store(); self.addCleanup(store.close)
        plan = Privacy(store).preview(owner=OWNER, contact=CONTACT)
        self.assertTrue(plan['can_apply'])
        self.assertEqual(0, sum(plan['counts'].values()))
        store.connection.execute("INSERT INTO messages VALUES ('1','s','t',?,?,?,'pending','f')", (OWNER, CONTACT, '2026-09-01'))
        with self.assertRaisesRegex(ValueError, 'pending'):
            Privacy(store).preview(owner=OWNER, contact=CONTACT)
        self.assertTrue(store.connection.in_transaction)
        store.connection.rollback()
        store.connection.execute('CREATE TABLE untracked_copies (body TEXT)')
        with self.assertRaisesRegex(ValueError, 'schema'):
            Privacy(store).preview(owner=OWNER, contact=CONTACT)
