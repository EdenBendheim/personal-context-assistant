"""Loopback-only, owner-scoped HTTP API for local draft review."""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import sys
from urllib.parse import parse_qs, urlsplit

from .drafts import DraftRequest
from .memory import nonempty
from .reviews import Reviews
from .store import Store


def fields(payload, required, optional=()):
    if not isinstance(payload, dict) or not set(required) <= payload.keys() or payload.keys() - set(required) - set(optional):
        raise ValueError("Missing or unknown request fields")
    return payload


class ReviewServer(HTTPServer):
    def __init__(self, db: Path, *, owner: str, port: int = 0):
        self.db = Path(db).resolve()
        if not self.db.is_file():
            raise ValueError("Import messages into an existing database first")
        self.owner = nonempty(owner, "Owner").casefold()
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)
        self.url = f"http://127.0.0.1:{self.server_port}"


class Handler(BaseHTTPRequestHandler):
    server_version = "PersonalContext"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format, *args):
        # Request paths can contain contact identifiers; don't log private review traffic.
        pass

    def reply(self, status, value):
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def guard(self):
        if self.headers.get("Host") != self.server.url.removeprefix("http://"):
            self.reply(403, {"error": "Unexpected Host"})
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.url:
            self.reply(403, {"error": "Unexpected Origin"})
            return False
        if not secrets.compare_digest(self.headers.get("Authorization", "").encode(), f"Bearer {self.server.token}".encode()):
            self.reply(401, {"error": "Local review token required"})
            return False
        return True

    def body(self):
        if self.headers.get("Transfer-Encoding") is not None:
            raise ValueError("Transfer encoding is unsupported")
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ValueError("Use application/json")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise ValueError("A valid Content-Length is required") from None
        if not 0 < length <= 131_072:
            raise ValueError("Request body must be between 1 and 131,072 bytes")
        try:
            return json.loads(self.rfile.read(length))
        except (ValueError, UnicodeError):
            raise ValueError("Request body must be valid UTF-8 JSON") from None

    def dispatch(self, method):
        if not self.guard():
            return
        store = None
        try:
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query, keep_blank_values=True)
            if any(len(values) != 1 for values in query.values()):
                raise ValueError("Repeated query parameters are unsupported")
            query = {key:values[0] for key,values in query.items()}
            if not self.server.db.is_file():
                raise ValueError("Local database no longer exists")
            store = Store(str(self.server.db))
            reviews = Reviews(store)
            owner = self.server.owner
            path = parsed.path.strip("/").split("/")
            if method == "GET" and path == ["api", "contacts"]:
                fields(query, ())
                rows = store.connection.execute("""SELECT contact, COUNT(*) AS messages, MAX(timestamp) AS last_message
                    FROM (SELECT recipient AS contact, timestamp FROM messages WHERE author = ?
                          UNION ALL SELECT author AS contact, timestamp FROM messages WHERE recipient = ?)
                    WHERE contact != ? GROUP BY contact ORDER BY contact""", (owner, owner, owner))
                result = dict(owner=owner, contacts=[dict(row) for row in rows])
            elif method == "GET" and path in (["api", "reviews"], ["api", "summary"]):
                fields(query, ("contact",))
                result = (reviews.list if path[1] == "reviews" else reviews.summary)(owner=owner, **query)
            elif method == "GET" and len(path) == 3 and path[:2] == ["api", "reviews"]:
                fields(query, ())
                result = reviews.get(path[2], owner=owner)
                result["feedback"] = reviews.feedback_history(path[2], owner=owner)
            elif method == "POST" and path == ["api", "reviews"]:
                fields(query, ())
                payload = fields(self.body(), ("contact", "before", "query"), ("mode", "limit"))
                result = reviews.create(DraftRequest(owner=owner, **payload))
            elif method == "POST" and len(path) == 4 and path[:2] == ["api", "reviews"]:
                fields(query, ())
                if path[3] == "edit":
                    payload = fields(self.body(), ("expected_revision", "text"))
                    result = reviews.edit(path[2], owner=owner, **payload)
                elif path[3] == "feedback":
                    payload = fields(self.body(), ("expected_revision", "decision"), ("retrieval", "style", "notes"))
                    result = reviews.feedback(path[2], owner=owner, **payload)
                else:
                    self.reply(404, {"error": "Unknown route"})
                    return
            else:
                self.reply(404, {"error": "Unknown route"})
                return
            self.reply(200, result)
        except (ValueError, TypeError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else "Invalid request field type"
            self.reply(409 if message.startswith(("Stale", "Context changed")) else 400, {"error": message})
        except sqlite3.Error:
            self.reply(500, {"error": "Local database operation failed"})
        finally:
            if store is not None:
                store.close()

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_OPTIONS(self):
        self.reply(405, {"error": "Cross-origin access is unsupported"})


def main():
    parser = argparse.ArgumentParser(description="Serve a private local draft review API")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--port", type=int, default=8765, help="Loopback port; 0 chooses an available port")
    args = parser.parse_args()
    try:
        server = ReviewServer(args.db, owner=args.owner, port=args.port)
    except (ValueError, OSError, OverflowError) as exc:
        parser.error(str(exc))
    print(f"Local review API: {server.url}\nBearer token: {server.token}", file=sys.stderr, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
