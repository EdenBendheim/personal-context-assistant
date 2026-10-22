from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from threading import Thread
import unittest
from unittest.mock import patch

from personal_context.local_embeddings import LocalEmbeddingConfig, OllamaEmbeddingProvider
from personal_context.local_model import LocalModelError


class LocalEmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.payload = {'embeddings': [[3, 4], [0, 2]]}
        self.status = 200
        self.content_type = 'application/json'
        self.requests = []
        test = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass

            def do_POST(self):
                test.requests.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                body = test.payload if isinstance(test.payload, bytes) else json.dumps(test.payload).encode()
                self.send_response(test.status)
                self.send_header('Content-Type', test.content_type)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.cleanup)
        self.config = LocalEmbeddingConfig('synthetic-fixture',
            endpoint=f'http://127.0.0.1:{self.server.server_port}', local_only_confirmed=True)

    def cleanup(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_http_contract_no_proxy_no_truncation_and_normalized_result(self):
        with patch.dict('os.environ', {'HTTP_PROXY': 'http://attacker.invalid:9999'}):
            vectors = OllamaEmbeddingProvider(self.config).embed(['meeting', 'appointment'])
        self.assertEqual([[.6, .8], [0., 1.]], vectors)
        path, payload = self.requests[0]
        self.assertEqual('/api/embed', path)
        self.assertEqual(['meeting', 'appointment'], payload['input'])
        self.assertIs(False, payload['truncate'])
        self.assertEqual('0', payload['keep_alive'])
        self.assertEqual('ollama_embed', OllamaEmbeddingProvider(self.config).describe()['backend'])

    def test_remote_cloud_unconfirmed_and_invalid_input_fail_before_network(self):
        for changes in ({'endpoint': 'https://example.com:443'}, {'model': 'embed:cloud'},
                        {'local_only_confirmed': False}, {'timeout': 61}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                LocalEmbeddingConfig(**(self.config.__dict__ | changes))
        for inputs in ([], [''], ['x' * 4097]):
            with self.assertRaises(ValueError): OllamaEmbeddingProvider(self.config).embed(inputs)
        self.assertEqual([], self.requests)

    def test_redirect_errors_and_malformed_vectors_fail_without_fallback(self):
        for status in (302, 404, 500):
            self.status = status
            with self.assertRaises(LocalModelError): OllamaEmbeddingProvider(self.config).embed(['a', 'b'])
        self.status = 200
        for payload in (b'not json', [], {'error': 'private diagnostic'}, {'embeddings': [[1, 0]]},
                        {'embeddings': [[0, 0], [1, 2]]}, {'embeddings': [[1, 2], [float('nan'), 1]]}):
            self.payload = payload
            with self.assertRaises(LocalModelError) as caught:
                OllamaEmbeddingProvider(self.config).embed(['a', 'b'])
            self.assertNotIn('private', str(caught.exception))
        self.payload = {'embeddings': [[1, 0], [0, 1]]}
        self.content_type = 'text/plain'
        with self.assertRaises(LocalModelError): OllamaEmbeddingProvider(self.config).embed(['a', 'b'])

    def test_timeout_redaction_and_response_budget(self):
        with patch('personal_context.local_embeddings.HTTPConnection.request', side_effect=TimeoutError('secret')):
            with self.assertRaisesRegex(LocalModelError, 'unavailable or timed out') as caught:
                OllamaEmbeddingProvider(self.config).embed(['a'])
        self.assertNotIn('secret', str(caught.exception))
        self.payload = b'x' * 129
        with patch('personal_context.local_embeddings.MAX_RESPONSE_BYTES', 128):
            with self.assertRaisesRegex(LocalModelError, 'byte budget'):
                OllamaEmbeddingProvider(self.config).embed(['a'])
