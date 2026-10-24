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

    def test_apply_removes_every_live_copy_and_preserves_other_contact(self):
        store = Store(); self.addCleanup(store.close)
        memory, review = seed(store)
        privacy = Privacy(store)
        before = privacy._snapshot()
        plan = privacy.preview(owner=OWNER, contact=CONTACT)
        receipt = privacy.apply(owner=OWNER, contact=CONTACT, expected_plan_sha256=plan['plan_sha256'], confirm=True)
        self.assertEqual(plan['counts'], receipt['deleted'])
        self.assertFalse(receipt['physical_erasure_guaranteed'])
        self.assertEqual(0, sum(privacy.preview(owner=OWNER, contact=CONTACT)['counts'].values()))
        self.assertEqual([], store.search('demo', owner=OWNER, contact=CONTACT, before='2026-10-01T00:00:00Z'))
        self.assertEqual(1, len(store.search('demo', owner=OWNER, contact=OTHER, before='2026-10-01T00:00:00Z')))
        with self.assertRaises(ValueError):
            Reviews(store).get(review['review_id'], owner=OWNER)
        with self.assertRaises(ValueError):
            Memory(store).history(memory['memory_id'])
        after = privacy._snapshot()
        untouched = [row for row in before['rows']['draft_reviews'] if row['contact'] == OTHER]
        self.assertEqual(untouched, after['rows']['draft_reviews'])
        self.assertFalse(store.connection.in_transaction)

    def test_confirmation_stale_plan_and_foreign_copies_cannot_delete(self):
        from unittest.mock import patch
        store = Store(); self.addCleanup(store.close)
        seed(store); privacy = Privacy(store)
        plan = privacy.preview(owner=OWNER, contact=CONTACT)
        with patch.object(privacy, '_delete_rows', side_effect=AssertionError('deleted without consent')):
            for confirm in (False, None, 1, 'yes'):
                with self.assertRaisesRegex(ValueError, 'confirmation'):
                    privacy.apply(owner=OWNER, contact=CONTACT, expected_plan_sha256=plan['plan_sha256'], confirm=confirm)
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                privacy.apply(owner=OWNER, contact=CONTACT, expected_plan_sha256='wrong', confirm=True)
        Reviews(store).create(DraftRequest(CONTACT, OWNER, '2026-09-04T00:00:00Z', 'demo'))
        before = privacy._snapshot()
        with self.assertRaisesRegex(ValueError, 'Stale'):
            privacy.apply(owner=OWNER, contact=CONTACT, expected_plan_sha256=plan['plan_sha256'], confirm=True)
        blocked = privacy.preview(owner=OWNER, contact=CONTACT)
        with self.assertRaisesRegex(ValueError, 'Other scopes'):
            privacy.apply(owner=OWNER, contact=CONTACT, expected_plan_sha256=blocked['plan_sha256'], confirm=True)
        self.assertEqual(before, privacy._snapshot())

    def test_failure_rolls_back_all_tables_and_restores_secure_delete_setting(self):
        from unittest.mock import patch
        store = Store(); self.addCleanup(store.close)
        seed(store); privacy = Privacy(store)
        before = privacy._snapshot(); plan = privacy.preview(owner=OWNER, contact=CONTACT)
        original = privacy._delete_rows
        def failed(selected):
            original(selected)
            raise OSError('simulated failure before commit')
        store.connection.execute('PRAGMA secure_delete = OFF')
        with patch.object(privacy, '_delete_rows', side_effect=failed):
            with self.assertRaisesRegex(OSError, 'simulated'):
                privacy.apply(owner=OWNER, contact=CONTACT, expected_plan_sha256=plan['plan_sha256'], confirm=True)
        self.assertEqual(before, privacy._snapshot())
        self.assertEqual(0, store.connection.execute('PRAGMA secure_delete').fetchone()[0])
        self.assertFalse(store.connection.in_transaction)

    def test_another_connection_invalidates_a_preview_without_deleting_new_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/'shared.sqlite')
            a, b = Store(path), Store(path)
            try:
                seed(a); privacy = Privacy(a)
                plan = privacy.preview(owner=OWNER, contact=CONTACT)
                with b.connection:
                    b.connection.execute("UPDATE draft_edits SET text='concurrent edit' WHERE revision=1")
                current = privacy._snapshot()
                with self.assertRaisesRegex(ValueError, 'Stale'):
                    privacy.apply(owner=OWNER, contact=CONTACT, expected_plan_sha256=plan['plan_sha256'], confirm=True)
                self.assertEqual(current, privacy._snapshot())
            finally: a.close(); b.close()
