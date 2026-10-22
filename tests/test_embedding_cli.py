from contextlib import redirect_stdout, redirect_stderr
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from personal_context.embedding_cli import main
from personal_context.store import Store
from test_context import message, PARAMS


class EmbeddingCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'messages #?.sqlite'
        store = Store(str(self.path)); store.ingest([message()]); store.close()
        self.requests = []; self.status = 200; test = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                test.requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                body = b'{"embeddings":[[1,0],[1,0]]}'
                self.send_response(test.status); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.cleanup)
        self.args = ['embedding-search', 'meeting', '--db', str(self.path), '--model', 'synthetic-fixture',
            '--endpoint', f'http://127.0.0.1:{self.server.server_port}', '--confirm-local-only']
        for key, value in PARAMS.items(): self.args += ['--' + key, value]

    def cleanup(self):
        self.server.shutdown(); self.thread.join(); self.server.server_close()

    def invoke(self, args):
        output, error = StringIO(), StringIO()
        with patch('sys.argv', args), redirect_stdout(output), redirect_stderr(error):
            try: main(); code = 0
            except SystemExit as exc: code = exc.code
        return code, output.getvalue(), error.getvalue()

    def test_cli_round_trip_has_provenance_and_cannot_write_database(self):
        original = self.path.read_bytes()
        code, output, error = self.invoke(self.args)
        self.assertEqual((0, ''), (code, error))
        report = json.loads(output)
        self.assertEqual('1', report['results'][0]['id'])
        self.assertEqual('gmail', report['results'][0]['source'])
        self.assertEqual('embedding_cosine', report['retrieval']['backend'])
        self.assertEqual(original, self.path.read_bytes())
        readonly = Store(str(self.path), readonly=True); self.addCleanup(readonly.close)
        with self.assertRaises(sqlite3.OperationalError): readonly.ingest([message('2')])

    def test_confirmation_and_missing_database_fail_before_inference(self):
        args = [arg for arg in self.args if arg != '--confirm-local-only']
        code, output, error = self.invoke(args)
        self.assertEqual((2, ''), (code, output)); self.assertIn('cloud disabled', error)
        missing = Path(self.tmp.name) / 'missing' / 'db.sqlite'
        args = self.args.copy(); args[args.index('--db') + 1] = str(missing)
        code, output, _ = self.invoke(args)
        self.assertEqual((2, ''), (code, output)); self.assertFalse(missing.parent.exists())
        self.assertEqual([], self.requests)

    def test_inference_error_exits_without_success_json_or_lexical_fallback(self):
        self.status = 500
        code, output, error = self.invoke(self.args)
        self.assertEqual((2, ''), (code, output)); self.assertIn('HTTP 500', error)
        self.assertEqual(1, len(self.requests))
