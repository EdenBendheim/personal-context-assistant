from pathlib import Path
import tempfile
import unittest

from personal_context.messages import Message, read_discord_csv, read_jsonl, read_mbox
from personal_context.store import Store


def message(id="1", **changes):
    fields = dict(id=id, source="gmail", thread="thread-1", author="me@example.invalid",
                  recipient="alex@example.invalid", timestamp="2026-09-01T10:00:00Z", body="demo Thursday :D")
    return Message.from_dict(fields | changes)


PARAMS = dict(owner="me@example.invalid", contact="alex@example.invalid", before="2026-09-04T00:00:00Z")


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.addCleanup(self.store.close)

    def test_no_cross_contact_or_future_leak(self):
        self.store.ingest([message(), message("2", recipient="riley@example.invalid"),
                           message("3", timestamp=PARAMS["before"]),
                           message("4", timestamp="2026-10-01T00:00:00Z"),
                           message("5", author="alex@example.invalid", recipient="me@example.invalid")])
        self.assertEqual({r["id"] for r in self.store.search("demo", **PARAMS)}, {"1", "5"})
        self.assertEqual([r["id"] for r in self.store.style_examples(**PARAMS)], ["1"])

    def test_quote_cleanup_deduplicates_reimport_with_new_id(self):
        first = message(body="thanks!\n\nOn Tuesday, Alex wrote:\n> previous text")
        self.assertEqual(first.body, "thanks!")
        self.assertEqual(self.store.ingest([first, message("other-id", body="thanks!")]), 1)
        self.assertEqual(self.store.ingest([first]), 0)

    def test_failed_export_rolls_back_entire_import(self):
        def malformed():
            yield message()
            yield message("2", timestamp="no date")
        with self.assertRaises(ValueError):
            self.store.ingest(malformed())
        self.assertEqual(self.store.style_examples(**PARAMS), [])

    def test_timezones_compare_instants(self):
        self.store.ingest([message(timestamp="2026-09-03T20:00:00-04:00")])
        self.assertEqual(self.store.style_examples(**PARAMS), [])

    def test_persistent_store_and_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            db = str(Path(folder) / "messages.db")
            store = Store(db)
            store.ingest([message()]); store.close()
            reopened = Store(db)
            try:
                result = reopened.search("Thursday", **PARAMS)[0]
                self.assertEqual((result["source"], result["thread"], result["id"]), ("gmail", "thread-1", "1"))
            finally:
                reopened.close()

    def test_import_formats(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "messages.csv"
            path.write_text('ID,Timestamp,Contents,Attachments\n42,2026-09-01 12:00:00,"hey, Thursday?",\n')
            discord = list(read_discord_csv(path, author=PARAMS["owner"], recipient=PARAMS["contact"], thread="channel-1"))
            self.assertEqual(discord[0].body, "hey, Thursday?")
            path = Path(folder) / "messages.mbox"
            path.write_text('From sender Tue Sep 01 10:00:00 2026\nFrom: me@example.invalid\nTo: alex@example.invalid\nDate: Tue, 1 Sep 2026 10:00:00 +0000\nMessage-ID: <test-1>\nContent-Type: text/plain; charset=utf-8\n\nThursday demo\n')
            mail = list(read_mbox(path))
            self.assertEqual(mail[0].recipient, PARAMS["contact"])
            self.assertIn("Thursday", mail[0].body)

    def test_invalid_fields_fail_before_storage(self):
        for changes in ({"body": ""}, {"author": 4}, {"timestamp": "2026-09-01T12:00:00"}):
            with self.assertRaises(ValueError):
                message(**changes)


if __name__ == "__main__":
    unittest.main()
