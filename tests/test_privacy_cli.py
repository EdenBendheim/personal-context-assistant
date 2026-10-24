from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from personal_context.privacy_cli import main
from personal_context.store import Store
from test_privacy import seed, OWNER, CONTACT, OTHER


class PrivacyCLITests(unittest.TestCase):
    def call(self, path, *extra):
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            try:
                main(['--db', str(path), '--owner', OWNER, '--contact', CONTACT, *extra])
                code = 0
            except SystemExit as exc:
                code = exc.code
        return code, output.getvalue(), errors.getvalue()

    def test_preview_and_explicit_apply_roundtrip_preserve_original_export(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'messages.sqlite'
            store = Store(str(path)); seed(store); store.close()
            export = Path(folder)/'original.jsonl'
            export.write_text('synthetic original export stays unchanged')
            before = path.read_bytes()
            code, output, _ = self.call(path)
            self.assertEqual(0, code)
            plan = json.loads(output)
            self.assertEqual(before, path.read_bytes())
            self.assertNotIn('private', output)
            self.assertEqual(2, self.call(path, '--apply-plan', plan['plan_sha256'])[0])
            self.assertEqual(before, path.read_bytes())
            code, output, _ = self.call(path, '--apply-plan', plan['plan_sha256'], '--confirm-delete')
            self.assertEqual(0, code)
            self.assertEqual(plan['counts'], json.loads(output)['deleted'])
            self.assertEqual('synthetic original export stays unchanged', export.read_text())
            store = Store(str(path), readonly=True)
            try:
                self.assertEqual(1, len(store.search('demo', owner=OWNER, contact=OTHER, before='2026-10-01T00:00:00Z')))
            finally: store.close()
            self.assertEqual(0, sum(json.loads(self.call(path)[1])['counts'].values()))

    def test_missing_store_and_invalid_confirmation_never_create_or_migrate_files(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'missing.sqlite'
            for flags in ((), ('--confirm-delete',), ('--apply-plan', '0'*64, '--confirm-delete')):
                code, output, _ = self.call(path, *flags)
                self.assertEqual(2, code)
                self.assertEqual('', output)
                self.assertFalse(path.exists())
            path = Path(folder)/'minimal.sqlite'
            Store(str(path)).close()
            before = path.read_bytes()
            self.assertEqual(0, self.call(path)[0])
            self.assertEqual(before, path.read_bytes())

    def test_stale_cli_plan_is_rejected_without_success_output_or_data_loss(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'messages.sqlite'
            store = Store(str(path)); seed(store)
            plan = json.loads(self.call(path)[1])
            with store.connection:
                store.connection.execute("UPDATE messages SET body='new message text' WHERE id='1'")
            store.close()
            before = path.read_bytes()
            code, output, errors = self.call(path, '--apply-plan', plan['plan_sha256'], '--confirm-delete')
            self.assertEqual(2, code)
            self.assertEqual('', output)
            self.assertIn('Stale', errors)
            self.assertEqual(before, path.read_bytes())
