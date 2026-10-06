import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from personal_context.draft_cli import main
from personal_context.drafts import CitedQuote, DraftEngine, DraftRequest, ExtractiveProvider
from personal_context.memory import Memory
from personal_context.messages import Message
from personal_context.store import Store


OWNER, CONTACT = "owner@example.invalid", "alex@example.invalid"
BEFORE = "2026-09-04T00:00:00Z"


def message(message_id="1", **changes):
    return Message.from_dict(dict(id=message_id, source="gmail", thread="demo", author=OWNER,
                                  recipient=CONTACT, timestamp="2026-09-01T10:00:00Z", body="demo Thursday :D") | changes)


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.addCleanup(self.store.close)
        self.store.ingest([message(), message("2", author=CONTACT, recipient=OWNER, body="demo: include retrieval"),
                           message("3", recipient="riley@example.invalid", body="secret demo for Riley"),
                           message("4", timestamp=BEFORE, body="future demo result")])
        self.memory = Memory(self.store)
        self.item = self.memory.create(owner=OWNER, contact=CONTACT, kind="fact", text="Demo is planned for Thursday.",
                                       sources=[("gmail", "1")], reason="Reviewed schedule", at="2026-09-02T00:00:00Z")
        self.engine = DraftEngine(self.store, self.memory)
        self.request = DraftRequest(OWNER, CONTACT, BEFORE, "demo")

    def test_personalized_packet_preserves_citations_scope_cutoff_and_owner_style(self):
        result = self.engine.draft(self.request)
        self.assertEqual("needs_review", result["status"])
        self.assertEqual(3, len(result["citations"]))
        self.assertEqual({"1", "2"}, {e["provenance"]["id"] for e in result["packet"]["evidence"] if e["kind"] == "message"})
        self.assertEqual(["1"], [e["id"] for e in result["packet"]["style_examples"]])
        self.assertTrue(all(e["author"] == OWNER for e in result["packet"]["style_examples"]))
        cited_memory = next(c for c in result["citations"] if c["kind"] == "memory")
        self.assertEqual(self.item["memory_id"], cited_memory["provenance"]["memory_id"])
        self.assertEqual("1", cited_memory["provenance"]["sources"][0]["message_id"])
        self.assertNotIn("secret", result["draft_text"])
        self.assertNotIn("future", result["draft_text"])
        self.assertEqual(result, self.engine.draft(self.request))

    def test_context_excludes_memory_and_style_and_generic_never_reads_history(self):
        contextual = self.engine.draft(DraftRequest(OWNER, CONTACT, BEFORE, "demo", mode="context"))
        self.assertEqual((), contextual["packet"]["style_examples"])
        self.assertTrue(all(e["kind"] == "message" for e in contextual["packet"]["evidence"]))
        with patch.object(self.store, "search", side_effect=AssertionError("history read")), \
                patch.object(self.memory, "context", side_effect=AssertionError("memory read")), \
                patch.object(self.store, "style_examples", side_effect=AssertionError("style read")):
            generic = self.engine.draft(DraftRequest(OWNER, CONTACT, BEFORE, "demo", mode="generic"))
        self.assertEqual([], generic["citations"])
        self.assertEqual((), generic["packet"]["evidence"])

    def test_no_history_and_style_only_history_abstain_before_calling_provider(self):
        class NeverCalled:
            def select_quotes(self, packet):
                raise AssertionError("provider should not run")
        for request in (DraftRequest(OWNER, "new@example.invalid", BEFORE, "demo"),
                        DraftRequest(OWNER, CONTACT, "2026-09-01T12:00:00Z", "unrelated topic")):
            result = self.engine.draft(request, NeverCalled())
            self.assertEqual("needs_history", result["status"])
            self.assertEqual("", result["draft_text"])
        self.assertTrue(result["packet"]["style_examples"])

    def test_unknown_fabricated_style_only_duplicate_and_unbounded_quotes_are_rejected(self):
        class BadProvider:
            def __init__(self, quotes):
                self.quotes = quotes
            def select_quotes(self, packet):
                return self.quotes
        for quotes in ([CitedQuote("unknown", "demo")], [CitedQuote("message-1", "I received a job offer")],
                       [CitedQuote("style-1", "demo")], [CitedQuote("message-1", "demo")]*2,
                       [CitedQuote("message-1", "demo")]*4, ["arbitrary uncited prose"]):
            with self.subTest(quotes=quotes), self.assertRaises(ValueError):
                self.engine.draft(self.request, BadProvider(quotes))

    def test_provider_receives_a_copy_and_cannot_replace_evidence_with_fabricated_text(self):
        class MutatingProvider:
            def select_quotes(self, packet):
                object.__setattr__(packet.evidence[0], "text", "fabricated fact")
                packet.style_examples[0]["body"] = "changed style"
                return [CitedQuote(packet.evidence[0].key, "fabricated fact")]
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.engine.draft(self.request, MutatingProvider())
        self.assertEqual("demo Thursday :D", self.store.style_examples(owner=OWNER, contact=CONTACT, before=BEFORE)[0]["body"])

    def test_memory_revocation_or_source_edit_during_provider_call_rejects_stale_packet(self):
        engine = self.engine
        memory_id = self.item["memory_id"]
        class RevokingProvider(ExtractiveProvider):
            def select_quotes(self, packet):
                engine.memory.revoke(memory_id, expected_revision=1, reason="Owner withdrew memory", at="2026-09-03T00:00:00Z")
                return super().select_quotes(packet)
        with self.assertRaisesRegex(ValueError, "Context changed"):
            self.engine.draft(self.request, RevokingProvider())
        class EditingProvider(ExtractiveProvider):
            def select_quotes(self, packet):
                with engine.store.connection:
                    engine.store.connection.execute("UPDATE messages SET body = 'changed demo source' WHERE id = '1'")
                return super().select_quotes(packet)
        with self.assertRaisesRegex(ValueError, "Context changed"):
            self.engine.draft(self.request, EditingProvider())

    def test_broken_retrieval_boundary_is_rejected(self):
        row = dict(self.store.connection.execute("SELECT * FROM messages WHERE id = '4'").fetchone())
        with patch.object(self.store, "search", return_value=[row]), self.assertRaisesRegex(ValueError, "boundary"):
            self.engine.prepare(self.request)
        row = dict(self.store.connection.execute("SELECT * FROM messages WHERE id = '3'").fetchone())
        with patch.object(self.store, "search", return_value=[row]), self.assertRaisesRegex(ValueError, "boundary"):
            self.engine.prepare(self.request)

    def test_request_validation_and_cli_do_not_create_a_missing_database(self):
        for changes in (dict(mode="invalid"), dict(limit=True), dict(limit=21), dict(before="2026-09-04"),
                        dict(query=" "), dict(contact=OWNER)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                DraftRequest(**(dict(owner=OWNER, contact=CONTACT, before=BEFORE, query="demo") | changes))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"messages.sqlite"
            arguments = ["draft", "--db", str(path), "--owner", OWNER, "--contact", CONTACT,
                         "--before", BEFORE, "--query", "demo"]
            with patch.object(sys, "argv", arguments), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main()
            self.assertFalse(path.exists())
            store = Store(str(path))
            store.ingest([message()])
            store.close()
            output = io.StringIO()
            with patch.object(sys, "argv", arguments), contextlib.redirect_stdout(output):
                main()
            result = json.loads(output.getvalue())
            self.assertEqual("needs_review", result["status"])
            self.assertEqual("1", result["citations"][0]["provenance"]["id"])


if __name__ == "__main__":
    unittest.main()
