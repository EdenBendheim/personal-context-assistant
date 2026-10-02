import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from personal_context.cli import main
from personal_context.imports import plan_import
from personal_context.messages import Message
from personal_context.store import Store


def record(id="1", **changes):
    return dict(id=id, source="gmail", thread="demo", author="owner@example.invalid",
                recipient="alex@example.invalid", timestamp="2026-09-01T00:00:00Z",
                body="Synthetic demo") | changes


class PreviewTests(unittest.TestCase):
    def test_preview_accounts_for_both_duplicate_keys_without_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "existing.sqlite"
            store = Store(str(db))
            store.ingest([Message.from_dict(record())])
            store.close()
            original = db.read_bytes()
            path = Path(folder) / "fixture.jsonl"
            rows = [record(), record(body="Conflicting ID"), record("2", body="New message"),
                    record("alias", body="New message"), record("3", body="Other message")]
            path.write_text("\n".join(map(json.dumps, rows)) + '\n\n{broken\n{"id":"missing"}\n')
            report = plan_import(path, db=db).report
            self.assertEqual((report["valid"], report["duplicates"], report["would_insert"],
                              report["invalid"], report["skipped"]), (5, 3, 2, 2, 1))
            self.assertEqual([error["record"] for error in report["errors"]], [7, 8])
            self.assertFalse(report["ready"])
            self.assertEqual(db.read_bytes(), original)

    def test_cli_preview_creates_no_database_or_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.jsonl"
            path.write_text(json.dumps(record()))
            db = Path(folder) / "absent" / "messages.sqlite"
            output = io.StringIO()
            with patch("sys.argv", ["personal-context", "--db", str(db), "import", str(path), "--preview"]):
                with contextlib.redirect_stdout(output):
                    main()
            report = json.loads(output.getvalue())
            self.assertEqual((report["would_insert"], report["inserted"], report["preview"]), (1, 0, True))
            self.assertFalse(db.parent.exists())

    def test_invalid_apply_reports_all_errors_and_leaves_existing_store_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path, db = Path(folder) / "fixture.jsonl", Path(folder) / "existing.sqlite"
            store = Store(str(db))
            store.ingest([Message.from_dict(record())]); store.close()
            original = db.read_bytes()
            path.write_text(json.dumps(record("2", body="Valid new message")) + '\n[]\n' +
                            json.dumps(record("3", timestamp="PRIVATE INVALID VALUE")))
            output = io.StringIO()
            with patch("sys.argv", ["personal-context", "--db", str(db), "import", str(path)]):
                with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as error:
                    main()
            self.assertEqual(error.exception.code, 2)
            report = json.loads(output.getvalue())
            self.assertEqual((report["invalid"], report["inserted"]), (2, 0))
            self.assertNotIn("PRIVATE", output.getvalue())
            self.assertEqual(db.read_bytes(), original)

    def test_csv_errors_are_collected_after_valid_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.csv"
            path.write_text('ID,Timestamp,Contents\n1,2026-09-01 12:00:00,hello\n2,bad,secret\n3,2026-09-01 13:00:00\n4,2026-09-01 14:00:00,\n')
            report = plan_import(path, db=Path(folder)/"absent.sqlite", format="discord-csv",
                                 owner="owner@example.invalid", contact="alex@example.invalid", thread="demo").report
            self.assertEqual((report["valid"], report["invalid"], report["skipped"]), (1, 2, 1))
            self.assertEqual([error["record"] for error in report["errors"]], [3, 4])

    def test_mbox_invalid_headers_and_unsupported_body_are_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.mbox"
            envelope = "From sender Tue Sep 01 10:00:00 2026\n"
            headers = "From: owner@example.invalid\nTo: alex@example.invalid\n"
            date = "Date: Tue, 1 Sep 2026 10:00:00 +0000\n"
            path.write_text(envelope+headers+"Content-Type: text/plain\n\nMissing date\n\n"+
                            envelope+headers+date+"Content-Type: text/plain\n\nValid demo\n\n"+
                            envelope+headers+date+"Content-Type: text/html\n\n<b>HTML only</b>\n\n"+
                            envelope+headers+date+'Content-Type: text/plain; charset="nonexistent-codec"\n\nBad charset\n')
            report = plan_import(path, db=Path(folder)/"absent.sqlite", format="mbox").report
            self.assertEqual((report["valid"], report["invalid"], report["skipped"]), (1, 2, 1))
            self.assertEqual([error["record"] for error in report["errors"]], [1, 4])

    def test_apply_valid_file_matches_preview_and_reimport_is_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            path, db = Path(folder)/"fixture.jsonl", Path(folder)/"new.sqlite"
            path.write_text(json.dumps(record()))
            output = io.StringIO()
            with patch("sys.argv", ["personal-context", "--db", str(db), "import", str(path)]):
                with contextlib.redirect_stdout(output):
                    main()
            self.assertEqual(json.loads(output.getvalue())["inserted"], 1)
            report = plan_import(path, db=db).report
            self.assertEqual((report["duplicates"], report["would_insert"]), (1, 0))


if __name__ == "__main__":
    unittest.main()
