from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from personal_context.import_staging import stage_records
from personal_context.messages import ImportRecord, Message
from test_import_preview import record


class ImportStagingTests(unittest.TestCase):
    def test_replays_normalized_records_and_removes_scratch_after_exit_or_scan_failure(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = [ImportRecord(1, message=Message.from_dict(record(body="Synthetic café"))),
                      ImportRecord(1, message=Message.from_dict(record("two", body="Synthetic second recipient"))),
                      ImportRecord(2, skipped="Blank line"), ImportRecord(3, error="Malformed JSON")]

            def temporary_directory(**kwargs):
                return TemporaryDirectory(dir=root, **kwargs)

            def interrupted_scan():
                yield source[0]
                raise OSError("Synthetic read failure")

            with patch("personal_context.import_staging.TemporaryDirectory", side_effect=temporary_directory):
                with stage_records(iter(source)) as stage:
                    self.assertEqual(source, list(stage.records()))
                    self.assertEqual(source, list(stage.records()))
                self.assertEqual([], list(root.iterdir()))
                with self.assertRaisesRegex(OSError, "Synthetic read failure"), stage_records(interrupted_scan()):
                    self.fail("A failed scan must never make a stage available")
                self.assertEqual([], list(root.iterdir()))
