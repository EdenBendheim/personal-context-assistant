from http.server import BaseHTTPRequestHandler, HTTPServer
import hashlib
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from personal_context.local_identity import inspect_model, verify_model_files
from personal_context.local_model import LocalModelConfig, LocalModelError


class LocalIdentityTests(unittest.TestCase):
    def setUp(self):
        self.digest = 'a'*64
        self.status = 200
        self.payloads = {'/api/version': dict(version='0.1.0'),
            '/api/tags': dict(models=[dict(name='synthetic:fixture', digest=self.digest, size=100)]),
            '/api/show': dict(details=dict(family='fixture', format='gguf'), capabilities=['completion'])}
        self.requests = []
        test = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self): self.answer()
            def do_POST(self): self.answer()
            def answer(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                test.requests.append((self.path, body))
                data = json.dumps(test.payloads[self.path]).encode()
                self.send_response(test.status); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)
        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.cleanup)
        self.config = LocalModelConfig('synthetic:fixture', endpoint=f'http://127.0.0.1:{self.server.server_port}', local_only_confirmed=True)

    def cleanup(self): self.server.shutdown(); self.thread.join(); self.server.server_close()

    def test_metadata_is_bounded_exact_and_contains_no_message_or_local_paths(self):
        with patch.dict('os.environ', {'HTTP_PROXY':'http://invalid.example:1'}):
            result = inspect_model(self.config, expected_digest=self.digest, capability='completion')
        self.assertEqual(self.digest, result['digest'])
        self.assertEqual('0.1.0', result['runtime_version'])
        self.assertEqual([('/api/version', b''), ('/api/tags', b''), ('/api/show', b'{"model": "synthetic:fixture"}')], self.requests)
        self.assertNotIn('modelfile', result)

    def test_changed_digest_remote_metadata_capability_and_status_are_rejected(self):
        for digest, capability in [('b'*64, 'completion'), (self.digest, 'embedding')]:
            with self.assertRaises(LocalModelError): inspect_model(self.config, expected_digest=digest, capability=capability)
        self.payloads['/api/show']['remote_host'] = 'outside.example'
        with self.assertRaises(LocalModelError): inspect_model(self.config)
        self.status = 302
        with self.assertRaises(LocalModelError): inspect_model(self.config)
        self.status = 200
        self.payloads['/api/version'] = dict(version='x'*1_048_577)
        with self.assertRaisesRegex(LocalModelError, '1 MiB'): inspect_model(self.config)

    def test_manifest_and_every_blob_are_read_only_verified_and_paths_are_redacted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'manifests').mkdir(); (root/'blobs').mkdir()
            data = b'synthetic model bytes'; digest = hashlib.sha256(data).hexdigest()
            blob = root/'blobs'/('sha256-'+digest); blob.write_bytes(data)
            layer = dict(digest='sha256:'+digest, size=len(data))
            manifest = root/'manifests'/'fixture'; manifest.write_text(json.dumps(dict(config=layer, layers=[layer])))
            identity = dict(digest=hashlib.sha256(manifest.read_bytes()).hexdigest())
            result = verify_model_files(identity, root, manifest)
            self.assertEqual(2, len(result['verified_blobs']))
            self.assertNotIn(folder, json.dumps(result))
            before = manifest.read_bytes()
            blob.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'blob bytes'): verify_model_files(identity, root, manifest)
            self.assertEqual(before, manifest.read_bytes())
            with self.assertRaises(ValueError): verify_model_files(identity, root, root/'outside')

    def test_retained_registry_manifest_requires_exact_wrapper_equivalence(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'manifests').mkdir(); (root/'blobs').mkdir()
            data=b'synthetic model'; digest=hashlib.sha256(data).hexdigest()
            (root/'blobs'/('sha256-'+digest)).write_bytes(data)
            layer=dict(digest='sha256:'+digest,size=len(data))
            original=dict(schemaVersion=2,config=layer,layers=[layer])
            raw=json.dumps(original).encode(); expected=hashlib.sha256(raw).hexdigest()
            (root/'blobs'/('sha256-'+expected)).write_bytes(raw)
            origin=dict(mediaType='application/vnd.docker.distribution.manifest.v2+json',digest='sha256:'+expected,size=len(raw))
            wrapper=original|dict(layers=[layer,origin]);path=root/'manifests'/'fixture'
            path.write_text(json.dumps(wrapper))
            result=verify_model_files(dict(digest=expected),root,path)
            self.assertEqual('retained_registry_manifest',result['digest_binding'])
            self.assertNotEqual(result['manifest_file_sha256'],result['manifest_sha256'])
            path.write_text(json.dumps(wrapper|dict(schemaVersion=3)))
            with self.assertRaisesRegex(ValueError,'wrapper differs'):
                verify_model_files(dict(digest=expected),root,path)
