import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from personal_context.memory import Memory
from personal_context.memory_cli import main
from personal_context.messages import Message
from personal_context.store import Store


OWNER, CONTACT = "owner@example.invalid", "alex@example.invalid"
T1, T2, T3, T4 = [f"2026-09-0{day}T12:00:00Z" for day in range(1, 5)]


def message(message_id="1", **changes):
    return Message.from_dict(dict(id=message_id, source="gmail", thread="demo",
                                  author=OWNER, recipient=CONTACT, timestamp=T1,
                                  body="Alex wants a Thursday demo.") | changes)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.store.ingest([message(), message("2", timestamp=T2, body="Actually Friday works better."),
                           message("3", recipient="riley@example.invalid", body="Another conversation.")])
        self.memory = Memory(self.store)

    def tearDown(self):
        self.store.close()

    def create(self, **changes):
        return self.memory.create(**(dict(owner=OWNER, contact=CONTACT, kind="preference",
                                          text="Alex wants a Thursday demo.", sources=[("gmail", "1")],
                                          reason="Reviewed message", at=T1) | changes))

    def context(self, **changes):
        return self.memory.context(**(dict(owner=OWNER, contact=CONTACT, before=T4) | changes))

    def test_corrections_keep_citations_and_respect_exclusive_cutoffs(self):
        initial = self.create(owner=" OWNER@EXAMPLE.INVALID ", contact=" ALEX@EXAMPLE.INVALID ")
        corrected = self.memory.revise(initial["memory_id"], expected_revision=1, text="Friday demo",
                                       sources=[("gmail", "2")], reason="Schedule changed", at=T2)
        self.assertEqual([], self.context(before=T1))
        self.assertEqual("Alex wants a Thursday demo.", self.context(before=T2)[0]["text"])
        self.assertEqual(corrected, self.context(before=T3)[0])
        self.assertEqual([], self.context(contact="riley@example.invalid"))
        history = self.memory.history(initial["memory_id"])
        self.assertEqual([1, 2], [item["revision"] for item in history])
        self.assertEqual("1", history[0]["sources"][0]["message_id"])
        self.assertEqual(message("2", timestamp=T2, body="Actually Friday works better.").fingerprint,
                         corrected["sources"][0]["fingerprint"])

    def test_invalid_sources_leave_no_orphaned_item(self):
        invalid = [[("gmail", "missing")], [("gmail", "3")], [("gmail", "2")], [],
                   [("gmail", "1"), ("gmail", "1")], ["gmail:1"]]
        for refs in invalid:
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                self.create(sources=refs)
        self.assertEqual(0, self.store.connection.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0])
        self.assertFalse(self.store.connection.in_transaction)

    def test_failed_edit_does_not_change_history(self):
        initial = self.create()
        for changes in (dict(expected_revision=2), dict(at=T1), dict(sources=[("gmail", "3")]),
                        dict(text=" "), dict(expected_revision=True)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.memory.revise(initial["memory_id"], **(dict(expected_revision=1, text="Correction",
                    sources=[("gmail", "1")], reason="Review", at=T2) | changes))
        self.assertEqual([initial], self.memory.history(initial["memory_id"]))

    def test_revoke_suppresses_historical_context_but_retains_audit(self):
        initial = self.create()
        revoked = self.memory.revoke(initial["memory_id"], expected_revision=1, reason="Withdrawn by owner", at=T3)
        self.assertEqual([], self.context())
        self.assertEqual([], self.context(before=T2))
        self.assertIsNone(revoked["text"])
        self.assertEqual([], revoked["sources"])
        self.assertEqual(initial, self.memory.history(initial["memory_id"])[0])
        with self.assertRaisesRegex(ValueError, "Revoked"):
            self.memory.revise(initial["memory_id"], expected_revision=2, text="Restore",
                               sources=[("gmail", "1")], reason="Review", at=T4)

    def test_removed_or_changed_sources_cannot_support_context(self):
        self.create()
        with self.store.connection:
            self.store.connection.execute("UPDATE messages SET body = 'Changed raw message' WHERE id = '1'")
        self.assertEqual([], self.context())
        with self.store.connection:
            self.store.connection.execute("DELETE FROM messages WHERE id = '1'")
        self.assertEqual([], self.context())
        self.assertEqual(1, self.store.connection.execute("SELECT COUNT(*) FROM memory_sources").fetchone()[0])

    def test_all_supporting_sources_must_remain_valid_and_limit_is_applied_after_validation(self):
        first = self.create(at=T2, sources=[("gmail", "1"), ("gmail", "2")])
        self.create(at=T3, sources=[("gmail", "2")], text="Newer fact")
        with self.store.connection:
            self.store.connection.execute("DELETE FROM messages WHERE id = '2'")
        self.assertEqual([], self.context(limit=1))
        self.create(at=T3, sources=[("gmail", "1")], text="Valid fact")
        self.assertEqual("Valid fact", self.context(limit=1)[0]["text"])
        self.assertEqual(2, len(self.memory.history(first["memory_id"])[0]["sources"]))

    def test_writes_do_not_commit_an_unrelated_transaction(self):
        self.store.connection.execute("UPDATE messages SET body = 'Pending edit' WHERE id = '1'")
        with self.assertRaisesRegex(ValueError, "pending"):
            self.create()
        with self.assertRaisesRegex(ValueError, "pending"):
            Memory(self.store)
        self.assertTrue(self.store.connection.in_transaction)
        self.store.connection.rollback()
        self.assertEqual("Alex wants a Thursday demo.", self.create()["text"])

    def test_persistence_and_stale_editor_across_connections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory)/"messages.sqlite")
            first = Store(path)
            first.ingest([message()])
            a = Memory(first)
            initial = a.create(owner=OWNER, contact=CONTACT, kind="fact", text="Demo Thursday",
                               sources=[("gmail", "1")], reason="Review", at=T1)
            second = Store(path)
            b = Memory(second)
            try:
                b.revise(initial["memory_id"], expected_revision=1, text="Corrected",
                         sources=[("gmail", "1")], reason="Review", at=T2)
                with self.assertRaisesRegex(ValueError, "Stale"):
                    a.revoke(initial["memory_id"], expected_revision=1, reason="Outdated editor", at=T3)
                self.assertEqual(2, a.context(owner=OWNER, contact=CONTACT, before=T4)[0]["revision"])
            finally:
                first.close()
                second.close()
            reopened = Store(path)
            try:
                self.assertEqual(2, len(Memory(reopened).history(initial["memory_id"])))
            finally:
                reopened.close()

    def test_cli_can_add_list_and_inspect_history_without_creating_missing_db(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"messages.sqlite"
            with patch.object(sys, "argv", ["memory", "--db", str(path), "history", "unknown"]), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main()
            self.assertFalse(path.exists())
            store = Store(str(path))
            store.ingest([message()])
            store.close()
            arguments = ["memory", "--db", str(path), "add", "--owner", OWNER, "--contact", CONTACT,
                         "--kind", "fact", "--text", "Demo Thursday", "--source", "gmail", "1",
                         "--reason", "Reviewed", "--at", T1]
            output = io.StringIO()
            with patch.object(sys, "argv", arguments), contextlib.redirect_stdout(output):
                main()
            created = json.loads(output.getvalue())
            for command in (["history", created["memory_id"]],
                            ["list", "--owner", OWNER, "--contact", CONTACT, "--before", T4]):
                output = io.StringIO()
                with patch.object(sys, "argv", ["memory", "--db", str(path)]+command), contextlib.redirect_stdout(output):
                    main()
                self.assertEqual([created], json.loads(output.getvalue()))


if __name__ == "__main__":
    unittest.main()
