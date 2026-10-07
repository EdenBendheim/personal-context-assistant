import unittest

from personal_context.memory_workspace import MemoryWorkspace
from personal_context.messages import Message
from personal_context.store import Store

OWNER, CONTACT = "owner@example.invalid", "alex@example.invalid"
BEFORE = "2026-09-04T00:00:00Z"


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.addCleanup(self.store.close)
        self.store.ingest([Message.from_dict(dict(id="1", source="gmail", thread="demo", author=OWNER,
            recipient=CONTACT, timestamp="2026-09-01T00:00:00Z", body="demo Thursday"))])
        self.workspace = MemoryWorkspace(self.store, owner=OWNER)

    def create(self):
        return self.workspace.create(contact=CONTACT, kind="fact", text="Demo is Thursday.",
            sources=[["gmail", "1"]], reason="Reviewed synthetic message")

    def test_memory_revision_cutoffs_sources_and_withdrawal(self):
        item = self.create()
        rid = item["memory_id"]
        self.assertTrue(item["eligible_at_cutoff"])
        self.assertFalse(self.workspace.list(contact=CONTACT, before=BEFORE)[0]["eligible_at_cutoff"])
        self.assertTrue(item["source_messages"][0]["current"])
        edited = self.workspace.revise(rid, expected_revision=1, text="Thursday demo confirmed.",
            sources=[["gmail", "1"]], reason="Clarified wording")
        self.assertEqual([1, 2], [r["revision"] for r in edited["history"]])
        self.assertEqual(1, self.workspace.get(rid, before=edited["effective_at"])["context_revision"])
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.workspace.withdraw(rid, expected_revision=1, reason="stale editor")
        withdrawn = self.workspace.withdraw(rid, expected_revision=2, reason="Owner withdrew fact")
        self.assertFalse(withdrawn["eligible_at_cutoff"])
        self.assertEqual("Demo is Thursday.", withdrawn["history"][0]["text"])

    def test_other_owner_and_moved_source_bodies_are_not_exposed(self):
        item = self.create()
        other = MemoryWorkspace(self.store, owner="other@example.invalid")
        with self.assertRaises(ValueError):
            other.get(item["memory_id"])
        with self.assertRaises(ValueError):
            other.withdraw(item["memory_id"], expected_revision=1, reason="wrong owner")
        with self.store.connection:
            self.store.connection.execute("UPDATE messages SET recipient = 'riley@example.invalid', body = 'private moved message'")
        changed = self.workspace.get(item["memory_id"])
        self.assertFalse(changed["eligible_at_cutoff"])
        self.assertIsNone(changed["source_messages"][0]["message"])
        self.assertNotIn("private moved message", str(changed))

    def test_changed_in_scope_sources_are_visible_but_marked_invalid(self):
        item = self.create()
        with self.store.connection:
            self.store.connection.execute("UPDATE messages SET body = 'demo Friday'")
        changed = self.workspace.get(item["memory_id"])
        self.assertFalse(changed["eligible_at_cutoff"])
        self.assertFalse(changed["source_messages"][0]["current"])
        self.assertEqual("demo Friday", changed["source_messages"][0]["message"]["body"])
