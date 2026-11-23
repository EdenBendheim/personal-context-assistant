import contextlib
import io
import json
from pathlib import Path
import tempfile
import sqlite3
import unittest
from unittest.mock import patch

from personal_context.cli import main
from personal_context.imports import apply_previewed_import, plan_import
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
                              report["invalid"], report["skipped"], report["conflicts"]), (5, 2, 2, 2, 1, 1))
            self.assertEqual([error["record"] for error in report["errors"]], [2, 7, 8])
            self.assertFalse(report["ready"])
            self.assertEqual(db.read_bytes(), original)

    def test_jsonl_preview_isolates_bad_utf8_lone_surrogates_and_duplicate_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path, db = Path(folder)/"fixture.jsonl", Path(folder)/"absent.sqlite"
            valid = json.dumps(record("first", body="Synthetic café 🗓️")).encode()
            undecodable = b'{"body":"PRIVATE_BAD_BYTES\xff"}'
            duplicate = b'{"PRIVATE_KEY":1,"PRIVATE_KEY":2}'
            escaped_surrogate = json.dumps(record("surrogate", body="\ud800")).encode()
            trailing = json.dumps(record("last", body="Later valid content")).encode()
            path.write_bytes(b'\xef\xbb\xbf' + b'\r\n'.join(
                [valid, undecodable, b'', duplicate, escaped_surrogate, trailing]))
            plan = plan_import(path, db=db)
            self.assertEqual(["first", "last"], [item.id for item in plan.messages])
            self.assertEqual(1, plan.report["skipped"])
            self.assertEqual([
                {"record": 2, "reason": "Invalid UTF-8"},
                {"record": 4, "reason": "Duplicate JSON field"},
                {"record": 5, "reason": "Invalid fields, empty body, or timestamp"},
            ], plan.report["errors"])
            self.assertFalse(plan.report["ready"])
            self.assertFalse(db.exists())

    def test_preview_uses_indexed_keys_in_one_snapshot_while_a_wal_writer_adds_a_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = root/"history.sqlite"
            store = Store(str(db))
            self.addCleanup(store.close)
            store.connection.execute("PRAGMA journal_mode = WAL")
            existing = Message.from_dict(record(body="Stored synthetic message"))
            pending = Message.from_dict(record("2", body="New synthetic content"))
            store.ingest([existing])
            queries = []
            connect = sqlite3.connect

            def open_reader(*args, **kwargs):
                connection = connect(*args, **kwargs)
                connection.set_trace_callback(queries.append)
                return connection

            def records():
                from personal_context.messages import ImportRecord
                yield ImportRecord(1, message=existing)
                store.ingest([pending])
                yield ImportRecord(2, message=pending)

            with patch("personal_context.imports._records", return_value=records()), \
                    patch("personal_context.imports.sqlite3.connect", side_effect=open_reader):
                plan = plan_import(root/"unused.jsonl", db=db)
            self.assertEqual(["2"], [message.id for message in plan.messages])
            self.assertEqual(1, plan.report["duplicates"])
            lookups = [sql for sql in queries if "FROM messages" in sql]
            self.assertTrue(all(" WHERE " in sql or "LIMIT 0" in sql for sql in lookups))
            self.assertTrue(any("WHERE source =" in sql for sql in lookups))
            self.assertTrue(any("WHERE fingerprint =" in sql for sql in lookups))

    def test_guarded_cli_apply_rejects_stale_input_and_wrong_database_without_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root/"fixture.jsonl"
            db = root/"target"/"messages.sqlite"
            path.write_text(json.dumps(record(body="Earlier synthetic wording")))
            preview = io.StringIO()
            args = ["personal-context", "--db", str(db), "import", str(path)]
            with patch("sys.argv", args+["--preview"]), contextlib.redirect_stdout(preview):
                main()
            digest = json.loads(preview.getvalue())["preview_sha256"]
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            other = root/"other"/"messages.sqlite"
            with self.assertRaisesRegex(ValueError, "preview is stale"):
                apply_previewed_import(path, db=other, expected_preview=digest)
            self.assertFalse(other.parent.exists())
            path.write_text(json.dumps(record(body="Different synthetic wording")))
            stderr = io.StringIO()
            with patch("sys.argv", args+["--expect-preview", digest]), contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as failure:
                    main()
            self.assertEqual(2, failure.exception.code)
            self.assertIn("run preview again", stderr.getvalue())
            self.assertNotIn("synthetic wording", stderr.getvalue())
            self.assertFalse(db.parent.exists())

            path.write_text(json.dumps(record(body="Earlier synthetic wording")))
            applied = io.StringIO()
            with patch("sys.argv", args+["--expect-preview", digest]), contextlib.redirect_stdout(applied):
                main()
            report = json.loads(applied.getvalue())
            self.assertEqual((1, digest), (report["inserted"], report["preview_sha256"]))
            with self.assertRaisesRegex(ValueError, "preview is stale"):
                apply_previewed_import(path, db=db, expected_preview=digest)

    def test_guarded_apply_rejects_concurrent_conflict_on_previously_duplicate_alias(self):
        from personal_context import imports

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path, db = root/"fixture.jsonl", root/"existing.sqlite"
            store = Store(str(db))
            self.addCleanup(store.close)
            store.ingest([Message.from_dict(record())])
            path.write_text("\n".join(map(json.dumps, [
                record("new", body="Synthetic candidate"), record("alias"),
            ])))
            plan = plan_import(path, db=db)
            self.assertEqual((1, 1), (plan.report["duplicates"], plan.report["would_insert"]))
            original = imports._inspect_path

            def concurrent_writer(*args):
                snapshot = original(*args)
                store.ingest([Message.from_dict(record("alias", body="Concurrent conflict"))])
                return snapshot

            with patch.object(imports, "_inspect_path", side_effect=concurrent_writer):
                with self.assertRaisesRegex(ValueError, "preview is stale"):
                    apply_previewed_import(path, db=db, expected_preview=plan.report["preview_sha256"])
            rows = store.connection.execute("SELECT id FROM messages ORDER BY id")
            self.assertEqual(["1", "alias"], [row[0] for row in rows])

    def test_error_sample_is_bounded_but_late_conflict_and_counts_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, db = root/"fixture.jsonl", root/"existing.sqlite"
            store = Store(str(db))
            try:
                store.ingest([Message.from_dict(record())])
            finally:
                store.close()
            path.write_text("[]\n"*103 + json.dumps(record(body="Changed synthetic content")))
            report = plan_import(path, db=db).report
            self.assertEqual(103, report["invalid"])
            self.assertEqual(1, report["conflicts"])
            self.assertEqual(100, len(report["errors"]))
            self.assertEqual(list(range(1, 101)), [row["record"] for row in report["errors"]])
            self.assertEqual(4, report["errors_omitted"])
            self.assertFalse(report["ready"])
            self.assertIsNone(report["preview_sha256"])

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

    def test_conflicting_ids_block_apply_without_persisting_candidates_or_values(self):
        with tempfile.TemporaryDirectory() as folder:
            db, path = Path(folder)/"existing.sqlite", Path(folder)/"fixture.jsonl"
            store = Store(str(db))
            store.ingest([Message.from_dict(record())]); store.close()
            original = db.read_bytes()
            path.write_text('\n'.join(map(json.dumps, [record("2", body="Valid candidate"),
                record(body="PRIVATE CHANGED MESSAGE")])))
            output = io.StringIO()
            with patch("sys.argv", ["personal-context", "--db", str(db), "import", str(path)]):
                with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as error:
                    main()
            self.assertEqual(2, error.exception.code)
            report = json.loads(output.getvalue())
            self.assertEqual((1, 1, 0, False), (report["conflicts"], report["would_insert"], report["inserted"], report["ready"]))
            self.assertNotIn("PRIVATE", output.getvalue())
            self.assertEqual(original, db.read_bytes())

    def test_alias_ids_remain_consistent_even_when_the_first_content_is_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            path, db = Path(folder)/"fixture.jsonl", Path(folder)/"absent.sqlite"
            path.write_text('\n'.join(map(json.dumps, [record(), record("alias"),
                record("alias", body="Different content under the same alias")])))
            report = plan_import(path, db=db).report
            self.assertEqual((3, 1, 1, 1, False), tuple(report[key] for key in (
                "valid", "duplicates", "conflicts", "would_insert", "ready")))
            self.assertEqual(3, report["errors"][0]["record"])
            self.assertFalse(db.exists())

    def test_apply_rechecks_conflicts_that_arrive_after_preview_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as folder:
            db, path = Path(folder)/"messages.sqlite", Path(folder)/"fixture.jsonl"
            first = Store(str(db)); self.addCleanup(first.close)
            first.ingest([Message.from_dict(record())])
            path.write_text(json.dumps(record("2", body="Planned message")))
            plan = plan_import(path, db=db)
            self.assertTrue(plan.report["ready"])
            second = Store(str(db))
            second.ingest([Message.from_dict(record("2", body="Arrived after preview"))]); second.close()
            with self.assertRaisesRegex(ValueError, "conflicts"):
                first.ingest([Message.from_dict(record("3", body="Must roll back")), *plan.messages])
            self.assertEqual(["1", "2"], [row["id"] for row in first.connection.execute("SELECT id FROM messages ORDER BY id")])
            self.assertEqual("Arrived after preview", first.connection.execute("SELECT body FROM messages WHERE id='2'").fetchone()[0])
            first.connection.execute("UPDATE messages SET body = 'pending edit' WHERE id='1'")
            with self.assertRaisesRegex(ValueError, "pending"):
                first.ingest(plan.messages)
            self.assertTrue(first.connection.in_transaction)
            first.connection.rollback()
            output, errors = io.StringIO(), io.StringIO()
            with patch("sys.argv", ["personal-context", "--db", str(db), "import", str(path)]), \
                    patch("personal_context.cli.plan_import", return_value=plan):
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), self.assertRaises(SystemExit) as error:
                    main()
            self.assertEqual(2, error.exception.code)
            self.assertEqual("", output.getvalue())
            self.assertIn("identifier conflicts", errors.getvalue())
            self.assertNotIn("Planned message", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
