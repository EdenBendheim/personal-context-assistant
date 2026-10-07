from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from personal_context.messages import Message
from personal_context.review_server import ReviewServer
from personal_context.reviews import Reviews
from personal_context.store import Store

OWNER, CONTACT = "owner@example.invalid", "alex@example.invalid"


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db = Path(self.directory.name)/"messages.sqlite"
        store = Store(str(self.db))
        store.ingest([Message.from_dict(dict(id="1", source="gmail", thread="demo", author=OWNER,
            recipient=CONTACT, timestamp="2026-09-01T10:00:00Z", body="demo Thursday :D")),
            Message.from_dict(dict(id="2", source="gmail", thread="other", author="other@example.invalid",
            recipient="third@example.invalid", timestamp="2026-09-01T10:00:00Z", body="private other pair"))])
        store.close()
        self.server = ReviewServer(self.db, owner=OWNER)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.directory.cleanup()

    def call(self, path, payload=None, headers=None, raw=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        auth = {"Authorization":f"Bearer {self.server.token}", "Content-Type":"application/json"}
        auth.update(headers or {})
        body = json.dumps(payload) if payload is not None else raw
        connection.request("POST" if body is not None else "GET", path, body, auth)
        response = connection.getresponse()
        status, data, response_headers = response.status, response.read(), dict(response.getheaders())
        result = json.loads(data) if response_headers["Content-Type"].startswith("application/json") else data.decode()
        connection.close()
        return status, result, response_headers

    def create(self):
        return self.call("/api/reviews", dict(contact=CONTACT, before="2026-09-04T00:00:00Z", query="demo"))

    def test_http_create_reopen_edit_feedback_and_owner_scoped_contacts(self):
        status, result, headers = self.call("/api/contacts")
        self.assertEqual(200, status)
        self.assertEqual([CONTACT], [x["contact"] for x in result["contacts"]])
        self.assertEqual("no-store", headers["Cache-Control"])
        status, review, _ = self.create()
        self.assertEqual(200, status)
        path = "/api/reviews/"+review["review_id"]
        self.assertEqual(review["original"], self.call(path)[1]["original"])
        edited = self.call(path+"/edit", dict(expected_revision=1, text="Thursday works!"))[1]
        self.assertEqual(2, edited["revision"])
        self.assertEqual(409, self.call(path+"/edit", dict(expected_revision=1, text="stale"))[0])
        self.assertEqual(200, self.call(path+"/feedback", dict(expected_revision=2, decision="usable"))[0])
        self.assertEqual(2, self.call(path)[1]["feedback"][0]["revision"])
        self.assertEqual({"usable":1}, self.call("/api/summary?contact="+CONTACT)[1]["decisions"])

    def test_http_rejects_bad_token_host_origin_and_malformed_requests(self):
        for headers, code in (({"Authorization":""}, 401), ({"Host":"attacker.invalid"}, 403),
                              ({"Origin":"https://attacker.invalid"}, 403)):
            self.assertEqual(code, self.call("/api/contacts", headers=headers)[0])
        for payload in ([], {}, dict(owner="other", contact=CONTACT, before="bad", query="demo"),
                        dict(contact=CONTACT, before="2026-09-04T00:00:00Z", query=[]),
                        dict(contact=CONTACT, before=[], query="demo")):
            self.assertEqual(400, self.call("/api/reviews", payload)[0])
        self.assertEqual(400, self.call("/api/reviews", raw="bad JSON")[0])
        self.assertEqual(400, self.call("/api/reviews", raw="x"*131073)[0])
        self.assertEqual(400, self.call("/api/reviews?contact=a&contact=b")[0])
        self.assertEqual(404, self.call("/unknown")[0])

    def test_other_owner_review_and_changed_context_cannot_be_accepted(self):
        store = Store(str(self.db))
        reviews = Reviews(store)
        from personal_context.drafts import DraftRequest
        other = reviews.create(DraftRequest("other@example.invalid", "third@example.invalid", "2026-09-04T00:00:00Z", "private"))
        self.assertEqual(400, self.call("/api/reviews/"+other["review_id"])[0])
        rid = self.create()[1]["review_id"]
        with store.connection:
            store.connection.execute("DELETE FROM messages WHERE id = '1'")
        store.close()
        self.assertFalse(self.call("/api/reviews/"+rid)[1]["context_current"])
        self.assertEqual(409, self.call("/api/reviews/"+rid+"/feedback", dict(expected_revision=1, decision="usable"))[0])

    def test_missing_database_is_not_created(self):
        missing = self.db.parent/"absent.sqlite"
        with self.assertRaises(ValueError):
            ReviewServer(missing, owner=OWNER)
        self.assertFalse(missing.exists())

    def test_browser_bootstrap_assets_and_history_are_guarded_and_uncached(self):
        status, html, headers = self.call("/", headers={"Authorization":""})
        self.assertEqual(200, status)
        self.assertIn(self.server.token, html)
        self.assertIn("nonce-", headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual("no-store", headers["Cache-Control"])
        for path in ("/", "/app.js", "/app.css"):
            self.assertEqual(403, self.call(path, headers={"Host":"attacker.invalid"})[0])
            self.assertEqual(403, self.call(path, headers={"Sec-Fetch-Site":"cross-site"})[0])
        js = self.call("/app.js", headers={"Authorization":""})[1]
        self.assertNotIn(self.server.token, js)
        rid = self.create()[1]["review_id"]
        self.assertEqual([1], [item["revision"] for item in self.call("/api/reviews/"+rid+"/history")[1]])

    def test_memory_http_correction_withdrawal_and_exclusive_cutoff(self):
        from datetime import datetime, timedelta, timezone
        before = (datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat()
        status, item, _ = self.call("/api/memory", dict(contact=CONTACT, kind="fact", text="Thursday demo.",
            sources=[["gmail", "1"]], reason="Synthetic review"))
        self.assertEqual(200, status)
        mid = item["memory_id"]
        self.assertFalse(self.call("/api/memory?contact="+CONTACT+"&before=2026-09-04T00:00:00Z")[1][0]["eligible_at_cutoff"])
        self.assertTrue(self.call("/api/memory/"+mid)[1]["eligible_at_cutoff"])
        rid = self.call("/api/reviews", dict(contact=CONTACT, before=before, query="demo"))[1]["review_id"]
        edit = dict(expected_revision=1, text="Thursday demo confirmed.", sources=[["gmail", "1"]], reason="Clarified")
        self.assertEqual(200, self.call("/api/memory/"+mid+"/edit", edit)[0])
        self.assertEqual(409, self.call("/api/memory/"+mid+"/edit", edit)[0])
        withdrawn = self.call("/api/memory/"+mid+"/withdraw", dict(expected_revision=2, reason="Withdrawn"))[1]
        self.assertEqual("revoked", withdrawn["status"])
        self.assertEqual([1, 2, 3], [x["revision"] for x in withdrawn["history"]])
        self.assertFalse(self.call("/api/reviews/"+rid)[1]["context_current"])
        invalid = dict(contact="riley@example.invalid", kind="fact", text="Wrong pair", sources=[["gmail", "1"]], reason="Invalid")
        self.assertEqual(400, self.call("/api/memory", invalid)[0])
