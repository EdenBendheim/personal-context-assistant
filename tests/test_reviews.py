from pathlib import Path
import tempfile
import unittest

from personal_context.drafts import DraftRequest
from personal_context.messages import Message
from personal_context.reviews import Reviews
from personal_context.store import Store

OWNER, CONTACT = "owner@example.invalid", "alex@example.invalid"


def seed(store):
    store.ingest([Message.from_dict(dict(id="1", source="gmail", thread="demo", author=OWNER,
        recipient=CONTACT, timestamp="2026-09-01T10:00:00Z", body="demo Thursday :D"))])


def request(**changes):
    return DraftRequest(**(dict(owner=OWNER, contact=CONTACT, before="2026-09-04T00:00:00Z", query="demo") | changes))


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.addCleanup(self.store.close)
        seed(self.store)
        self.reviews = Reviews(self.store)

    def test_edits_preserve_original_packet_and_history_and_detect_source_changes(self):
        initial = self.reviews.create(request())
        rid = initial["review_id"]
        edited = self.reviews.edit(rid, owner=OWNER, expected_revision=1, text="  Friday works!\n")
        self.assertEqual(2, edited["revision"])
        self.assertEqual("  Friday works!\n", edited["text"])
        self.assertEqual(initial["original"], edited["original"])
        self.assertEqual([initial["text"], edited["text"]], [x["text"] for x in self.reviews.history(rid, owner=OWNER)])
        self.assertTrue(edited["context_current"])
        with self.store.connection:
            self.store.connection.execute("UPDATE messages SET body = 'demo changed' WHERE id = '1'")
        self.assertFalse(self.reviews.get(rid, owner=OWNER)["context_current"])
        self.assertEqual(initial["original"], self.reviews.get(rid, owner=OWNER)["original"])

    def test_scope_stale_invalid_and_noop_edits(self):
        initial = self.reviews.create(request())
        rid = initial["review_id"]
        for changes in (dict(owner="other@example.invalid"), dict(expected_revision=2),
                        dict(expected_revision=True), dict(text=" "), dict(text="x"*100001)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.reviews.edit(rid, **(dict(owner=OWNER, expected_revision=1, text="hello") | changes))
        with self.assertRaises(ValueError):
            self.reviews.history(rid, owner="other@example.invalid")
        self.assertEqual([], self.reviews.list(owner=OWNER, contact="riley@example.invalid"))
        self.assertEqual([], self.reviews.list(owner="other@example.invalid", contact=CONTACT))
        self.assertEqual(initial, self.reviews.edit(rid, owner=OWNER, expected_revision=1, text=initial["text"]))
        self.assertEqual(1, len(self.reviews.history(rid, owner=OWNER)))

    def test_cold_start_is_not_saved_and_pending_transactions_are_not_committed(self):
        self.assertEqual("needs_history", self.reviews.create(request(query="unknown"))["status"])
        self.assertEqual([], self.reviews.list(owner=OWNER, contact=CONTACT))
        self.store.connection.execute("UPDATE messages SET body = 'pending' WHERE id = '1'")
        with self.assertRaisesRegex(ValueError, "pending"):
            self.reviews.create(request())
        self.assertTrue(self.store.connection.in_transaction)
        self.store.connection.rollback()

    def test_persistence_and_stale_editor_between_connections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory)/"reviews.sqlite")
            a, b = Store(path), Store(path)
            try:
                seed(a)
                first, second = Reviews(a), Reviews(b)
                initial = first.create(request())
                rid = initial["review_id"]
                second.edit(rid, owner=OWNER, expected_revision=1, text="edited elsewhere")
                with self.assertRaisesRegex(ValueError, "Stale"):
                    first.edit(rid, owner=OWNER, expected_revision=1, text="outdated")
            finally:
                a.close()
                b.close()
            reopened = Store(path)
            try:
                self.assertEqual("edited elsewhere", Reviews(reopened).get(rid, owner=OWNER)["text"])
            finally:
                reopened.close()

    def test_feedback_is_revision_bound_and_repeated_ratings_do_not_inflate_summary(self):
        review = self.reviews.create(request())
        rid = review["review_id"]
        for decision in ("needs_work", "usable"):
            self.reviews.feedback(rid, owner=OWNER, expected_revision=1, decision=decision,
                                  retrieval="useful", style="needs_edit", notes="synthetic review")
        summary = self.reviews.summary(owner=OWNER, contact=CONTACT)
        self.assertEqual(1, summary["rated_current_revisions"])
        self.assertEqual({"usable": 1}, summary["decisions"])
        self.assertEqual(1.0, summary["mean_word_overlap"])
        self.reviews.edit(rid, owner=OWNER, expected_revision=1, text="Hey, Thursday works!")
        summary = self.reviews.summary(owner=OWNER, contact=CONTACT)
        self.assertEqual(0, summary["rated_current_revisions"])
        self.assertEqual(1, summary["changed_drafts"])
        self.assertEqual([1, 1], [x["revision"] for x in self.reviews.feedback_history(rid, owner=OWNER)])
        self.assertEqual(0, self.reviews.summary(owner=OWNER, contact="other@example.invalid")["reviews"])

    def test_feedback_rejects_stale_context_scope_revisions_and_invalid_ratings(self):
        rid = self.reviews.create(request())["review_id"]
        for changes in (dict(owner="other@example.invalid"), dict(expected_revision=2),
                        dict(decision="sent"), dict(retrieval="excellent"), dict(style="bad"), dict(notes="x"*2001)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.reviews.feedback(rid, **(dict(owner=OWNER, expected_revision=1, decision="usable") | changes))
        with self.store.connection:
            self.store.connection.execute("DELETE FROM messages")
        with self.assertRaisesRegex(ValueError, "Context changed"):
            self.reviews.feedback(rid, owner=OWNER, expected_revision=1, decision="usable")
        self.reviews.feedback(rid, owner=OWNER, expected_revision=1, decision="rejected", retrieval="incorrect")
        self.assertEqual(1, len(self.reviews.feedback_history(rid, owner=OWNER)))
