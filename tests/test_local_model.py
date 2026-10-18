from http.server import BaseHTTPRequestHandler,HTTPServer
import json
from threading import Thread
import unittest
from unittest.mock import patch

from personal_context.drafts import DraftEngine,DraftRequest
from personal_context.generation import generate
from personal_context.local_model import LocalModelConfig,LocalModelError,OllamaProvider
from personal_context.store import Store
from test_drafts import OWNER,CONTACT,BEFORE,message
from test_generation_format import wire


class LocalModelTests(unittest.TestCase):
    def setUp(self):
        self.store=Store();self.addCleanup(self.store.close);self.store.ingest([message()])
        self.engine=DraftEngine(self.store);self.request=DraftRequest(OWNER,CONTACT,BEFORE,'demo')
        self.status=200;self.content_type='application/json';self.payload=dict(done=True,done_reason='stop',message=dict(role='assistant',content=json.dumps(wire())))
        self.requests=[];test=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                test.requests.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                body=json.dumps(test.payload).encode() if not isinstance(test.payload,bytes) else test.payload
                self.send_response(test.status);self.send_header('Content-Type',test.content_type);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        self.server=HTTPServer(('127.0.0.1',0),Handler);self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.cleanup)
        self.config=LocalModelConfig('synthetic-fixture',endpoint=f'http://127.0.0.1:{self.server.server_port}',local_only_confirmed=True)

    def cleanup(self):self.server.shutdown();self.thread.join();self.server.server_close()

    def test_real_loopback_round_trip_bounded_settings_provenance_and_no_proxy(self):
        with patch.dict('os.environ',{'HTTP_PROXY':'http://attacker.invalid:9999'}):
            result=generate(self.engine,self.request,OllamaProvider(self.config))
        path,body=self.requests[0];self.assertEqual('/api/chat',path)
        self.assertFalse(body['stream']);self.assertEqual(0,body['keep_alive']);self.assertEqual(1024,body['options']['num_predict'])
        self.assertEqual('fact',body['format']['properties']['segments']['items']['properties']['kind']['enum'][0])
        self.assertEqual('The demo is Thursday.',result['draft_text'])
        self.assertEqual('synthetic-fixture',result['generation_provenance']['settings']['model'])
        self.assertTrue(result['support_review_required'])

    def test_remote_cloud_unconfirmed_and_unbounded_settings_fail_before_network(self):
        for changes in (dict(endpoint='https://example.com:443'),dict(endpoint='http://localhost:11434'),
            dict(endpoint='http://127.0.0.1:1/api'),dict(endpoint='http://user@127.0.0.1:1'),dict(endpoint='http://127.0.0.1:0'),
            dict(model='model:cloud'),dict(local_only_confirmed=False),dict(timeout=True),dict(timeout=61),dict(max_tokens=0),dict(seed=-1)):
            with self.subTest(changes=changes),self.assertRaises(ValueError):LocalModelConfig(**(self.config.__dict__|changes))
        self.assertEqual([],self.requests)

    def test_status_redirect_invalid_truncated_tool_and_oversized_responses_fail_closed(self):
        for status in (302,404,500):
            self.status=status
            with self.assertRaises(LocalModelError):generate(self.engine,self.request,OllamaProvider(self.config))
        self.status=200
        original=self.payload
        variants=[b'not json',original|dict(done=False),original|dict(done_reason='length'),
            original|dict(message=dict(role='assistant',content='{}',tool_calls=[{}])),
            original|dict(message=dict(role='assistant',content='x'*70000)),original|dict(message=dict(role='assistant',content='{}'))]
        for payload in variants:
            self.payload=payload
            with self.assertRaises(ValueError):generate(self.engine,self.request,OllamaProvider(self.config))
        self.payload=original;self.content_type='text/plain'
        with self.assertRaises(LocalModelError):generate(self.engine,self.request,OllamaProvider(self.config))

    def test_transport_timeout_is_redacted_and_prompt_budget_prevents_network(self):
        with patch('personal_context.local_model.HTTPConnection.request',side_effect=TimeoutError('secret diagnostic')):
            with self.assertRaisesRegex(LocalModelError,'unavailable or timed out') as caught:
                generate(self.engine,self.request,OllamaProvider(self.config))
        self.assertNotIn('secret',str(caught.exception))
        from dataclasses import replace
        with self.assertRaisesRegex(LocalModelError,'6,000-byte'):
            generate(self.engine,replace(self.request,query='demo '+'x'*6000),OllamaProvider(self.config))
        self.assertEqual([],self.requests)
