from contextlib import closing
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from personal_context.imports import MAX_REVIEW_IMPORT_BYTES
from personal_context.review_server import ReviewServer
from personal_context.store import Store

from test_review_import import CONTACT, OWNER, message


class ReviewImportServerTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.db = Path(folder) / "review.sqlite"
        Store(str(self.db)).close()
        self.server = self.enterContext(ReviewServer(self.db, owner=OWNER))
        thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.shutdown)

    def request(self, path, payload=None, **headers):
        request_headers = {"Authorization": f"Bearer {self.server.token}"}
        if payload is not None:
            request_headers["Content-Type"] = "application/x-ndjson"
        request_headers.update(headers)
        with closing(HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)) as client:
            client.request("GET" if payload is None else "POST", path, body=payload, headers=request_headers)
            response = client.getresponse()
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            return response.status, json.loads(response.read())

    def test_preview_requires_local_authenticated_upload_and_bounded_raw_jsonl(self):
        route = "/api/import/preview"
        payload = message("first")
        original = self.db.read_bytes()
        for headers, code in [
            ({"Authorization": ""}, 401),
            ({"Origin": "https://other.invalid"}, 403),
            ({"Host": "other.invalid"}, 403),
            ({"Sec-Fetch-Site": "cross-site"}, 403),
            ({"Content-Type": "application/json"}, 400),
            ({"Content-Encoding": "gzip"}, 400),
            ({"Content-Length": str(MAX_REVIEW_IMPORT_BYTES + 1)}, 400),
            ({"Transfer-Encoding": "chunked"}, 400),
        ]:
            with self.subTest(headers=headers):
                self.assertEqual(self.request(route, payload, **headers)[0], code)
        self.assertEqual(self.request(route + "?owner=other", payload)[0], 400)
        self.assertEqual(self.request("/api/import/unknown", payload)[0], 404)
        status, report = self.request(route, payload + b"\n{bad\xff}")
        self.assertEqual(status, 200)
        self.assertEqual(report["errors"], [{"record": 2, "reason": "Invalid UTF-8"}])
        self.assertEqual(self.db.read_bytes(), original)

    def test_apply_uses_review_owner_and_rejects_stale_or_missing_digest(self):
        payload = message("first")
        apply = "/api/import/apply"
        status, report = self.request("/api/import/preview", payload)
        self.assertEqual(status, 200)
        self.assertEqual(report["would_insert"], 1)
        self.assertEqual(self.request(apply, payload)[0], 400)
        header = {"X-Import-Preview": report["preview_sha256"]}
        self.assertEqual(self.request(apply, message("second"), **header)[0], 409)
        unrelated = message("unrelated", author=CONTACT, recipient="foreign@example.invalid")
        self.assertEqual(self.request(apply, b"\n".join([payload, unrelated]), **header)[0], 409)
        status, contacts = self.request("/api/contacts")
        self.assertEqual((status, contacts["contacts"]), (200, []))
        status, result = self.request(apply, payload, **header)
        self.assertEqual((status, result["inserted"]), (200, 1))
        self.assertEqual(self.request(apply, payload, **header)[0], 409)
        self.assertEqual(self.request("/api/contacts")[1]["contacts"][0]["contact"], CONTACT)
