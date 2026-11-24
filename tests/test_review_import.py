import json
from pathlib import Path
import tempfile
import unittest

from personal_context.imports import MAX_REVIEW_IMPORT_BYTES, preview_import, preview_review_import


OWNER = "owner@example.invalid"
CONTACT = "contact@example.invalid"


def message(identifier, **changes):
    return json.dumps(dict(id=identifier, source="synthetic", thread="test", author=OWNER,
                           recipient=CONTACT, timestamp="2026-11-23T00:00:00Z",
                           body="Synthetic test message") | changes).encode()


class ReviewImportTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.db = Path(folder) / "review.sqlite"

    def test_mixed_and_malformed_rows_block_preview_without_leaking_content(self):
        payload = b"\xef\xbb\xbf" + b"\r\n".join([
            message("outbound"), b"", b'{"body":"\xff"}',
            message("foreign", author="foreign@example.invalid"),
            message("inbound", author=CONTACT, recipient=OWNER, body="Another synthetic message"),
        ])
        report = preview_review_import(payload, db=self.db, owner=OWNER.upper())
        self.assertEqual((report["would_insert"], report["skipped"], report["invalid"]), (2, 1, 2))
        self.assertEqual(report["errors"], [
            {"record": 3, "reason": "Invalid UTF-8"},
            {"record": 4, "reason": "Message does not involve the review owner"},
        ])
        self.assertIsNone(report["preview_sha256"])
        self.assertFalse(report["ready"])
        self.assertFalse(self.db.exists())

    def test_digest_is_bound_to_normalized_owner_and_separate_from_cli(self):
        payload = message("one")
        export = self.db.with_suffix(".jsonl")
        export.write_bytes(payload)

        def digest(owner):
            report = preview_review_import(payload, db=self.db, owner=owner)
            self.assertTrue(report["ready"])
            return report["preview_sha256"]

        self.assertEqual(digest(OWNER), digest(f" {OWNER.upper()} "))
        self.assertNotEqual(digest(OWNER), digest(CONTACT))
        self.assertNotEqual(digest(OWNER), preview_import(export, db=self.db)["preview_sha256"])

    def test_empty_and_oversize_uploads_are_rejected(self):
        for payload in (b"", b"x" * (MAX_REVIEW_IMPORT_BYTES + 1)):
            with self.subTest(size=len(payload)), self.assertRaisesRegex(ValueError, "between 1 and"):
                preview_review_import(payload, db=self.db, owner=OWNER)
