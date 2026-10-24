from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

from personal_context import maintenance
from personal_context.maintenance import rebuild_indexes
from personal_context.memory import Memory
from personal_context.privacy import Privacy
from personal_context.reviews import Reviews
from personal_context.store import Store
from test_privacy import seed, OWNER, CONTACT, OTHER


class MaintenanceTests(unittest.TestCase):
    def test_rebuild_preserves_data_reviews_memories_retrieval_and_plan_identity(self):
        store = Store(); self.addCleanup(store.close)
        item, review = seed(store)
        parameters = dict(owner=OWNER, contact=CONTACT, before='2026-10-01T00:00:00Z')
        expected = store.search('demo', **parameters)
        memory = Memory(store).history(item['memory_id'])
        saved = Reviews(store).get(review['review_id'], owner=OWNER)
        privacy = Privacy(store)
        plan = privacy.preview(owner=OWNER, contact=CONTACT)
        report = rebuild_indexes(store)
        self.assertGreater(report['indexes_rebuilt'], 3)
        self.assertTrue(report['application_records_unchanged'])
        self.assertEqual(expected, store.search('demo', **parameters))
        self.assertEqual(memory, Memory(store).history(item['memory_id']))
        self.assertEqual(saved, Reviews(store).get(review['review_id'], owner=OWNER))
        self.assertEqual(plan, privacy.preview(owner=OWNER, contact=CONTACT))
        privacy.apply(owner=OWNER, contact=CONTACT, expected_plan_sha256=plan['plan_sha256'], confirm=True)
        self.assertTrue(rebuild_indexes(store)['application_records_unchanged'])
        self.assertEqual(1, len(store.search('demo', **(parameters | dict(contact=OTHER)))))

    def test_pending_work_integrity_failures_and_unexpected_record_changes_roll_back(self):
        store = Store(); self.addCleanup(store.close)
        seed(store); privacy = Privacy(store)
        before = privacy._snapshot()
        def mutated(connection):
            connection.execute("DELETE FROM messages WHERE id='1'")
        with patch.object(maintenance, '_reindex', side_effect=mutated):
            with self.assertRaisesRegex(ValueError, 'changed application records'):
                rebuild_indexes(store)
        self.assertEqual(before, privacy._snapshot())
        with patch.object(maintenance, '_integrity', side_effect=ValueError('integrity failure')):
            with self.assertRaisesRegex(ValueError, 'integrity'):
                rebuild_indexes(store)
        self.assertEqual(before, privacy._snapshot())
        store.connection.execute("UPDATE messages SET body='pending'")
        with self.assertRaisesRegex(ValueError, 'pending'):
            rebuild_indexes(store)
        self.assertTrue(store.connection.in_transaction)
        store.connection.rollback()

    def test_existing_only_cli_and_json_report(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'messages.sqlite'
            for exists in (False, True):
                if exists:
                    store = Store(str(path)); seed(store); store.close()
                output, errors = StringIO(), StringIO()
                with redirect_stdout(output), redirect_stderr(errors):
                    if exists:
                        maintenance.main(['--db', str(path), '--rebuild-indexes'])
                        self.assertEqual('ok', json.loads(output.getvalue())['integrity'])
                    else:
                        with self.assertRaises(SystemExit):
                            maintenance.main(['--db', str(path), '--rebuild-indexes'])
                        self.assertFalse(path.exists())
