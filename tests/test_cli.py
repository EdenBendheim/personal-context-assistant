import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from personal_context.cli import main
from personal_context.messages import Message
from personal_context.store import Store

OWNER, CONTACT = "owner@example.invalid", "alex@example.invalid"


def invoke(db, command, **changes):
    params = dict(owner=OWNER, contact=CONTACT, before="2026-09-04T00:00:00Z", limit=5) | changes
    args = ["personal-context", "--db", str(db), command]
    if command == "search":
        args.append("demo")
    for key, value in params.items():
        args += ["--"+key, str(value)]
    output, errors = io.StringIO(), io.StringIO()
    code = 0
    with patch("sys.argv", args), contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        try:
            main()
        except SystemExit as exc:
            code = exc.code
    return code, output.getvalue(), errors.getvalue()


class LookupCliTests(unittest.TestCase):
    def test_missing_lookup_store_never_creates_a_database_or_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"missing"/"messages.sqlite"
            for command in ("search", "style"):
                with self.subTest(command=command):
                    code, output, errors = invoke(path, command)
                    self.assertEqual((2, ""), (code, output))
                    self.assertIn("existing database", errors)
                    self.assertFalse(path.parent.exists())

    def test_both_lookup_commands_use_query_only_and_preserve_results_and_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"records #1.sqlite"
            store = Store(str(path))
            store.ingest([Message.from_dict(dict(id="1", source="synthetic", thread="demo",
                author=OWNER, recipient=CONTACT, timestamp="2026-09-01T00:00:00Z", body="demo Thursday"))])
            store.close()
            original_bytes = path.read_bytes()
            for command, method in (("search", "search"), ("style", "style_examples")):
                original_method = getattr(Store, method)
                calls = []
                def checked_lookup(instance, *args, **kwargs):
                    self.assertEqual(1, instance.connection.execute("PRAGMA query_only").fetchone()[0])
                    with self.assertRaises(sqlite3.OperationalError):
                        instance.connection.execute("DELETE FROM messages")
                    calls.append(True)
                    return original_method(instance, *args, **kwargs)
                with self.subTest(command=command), patch.object(Store, method, checked_lookup):
                    code, output, errors = invoke(path, command)
                    self.assertEqual((0, ""), (code, errors))
                    self.assertEqual(["1"], [item["id"] for item in json.loads(output)])
                    self.assertEqual([True], calls)
                    self.assertEqual(original_bytes, path.read_bytes())

    def test_bad_parameters_or_unrelated_schema_fail_without_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"messages.sqlite"
            store = Store(str(path)); store.close()
            original = path.read_bytes()
            for changes in (dict(before="not-a-date"), dict(limit=0), dict(contact=OWNER)):
                with self.subTest(changes=changes):
                    code, output, errors = invoke(path, "search", **changes)
                    self.assertEqual((2, ""), (code, output))
                    self.assertNotIn("Traceback", errors)
                    self.assertEqual(original, path.read_bytes())
            unrelated = Path(folder)/"unrelated.sqlite"
            with sqlite3.connect(unrelated) as connection:
                connection.execute("CREATE TABLE unrelated (value TEXT)")
            original = unrelated.read_bytes()
            code, output, errors = invoke(unrelated, "style")
            self.assertEqual((2, ""), (code, output))
            self.assertIn("supported database", errors)
            self.assertEqual(original, unrelated.read_bytes())


if __name__ == "__main__":
    unittest.main()
