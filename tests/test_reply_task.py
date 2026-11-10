from dataclasses import asdict, replace
import hashlib
import json
import unittest

from personal_context.drafts import DraftEngine, DraftRequest, packet_dict
from personal_context.generation_format import prompt_messages
from personal_context.reviews import Reviews
from personal_context.store import Store
from test_drafts import OWNER, CONTACT, BEFORE, message


class ReplyTaskTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.addCleanup(self.store.close)
        self.store.ingest([message()])
        self.request = DraftRequest(OWNER, CONTACT, BEFORE, 'demo')
        self.engine = DraftEngine(self.store)

    def test_absent_fields_preserve_legacy_wire_fingerprint_and_saved_review_currentness(self):
        packet = self.engine.prepare(self.request)
        legacy = asdict(packet)
        legacy['request'].pop('current_message')
        legacy['request'].pop('intent')
        self.assertEqual(legacy, packet_dict(packet))
        self.assertEqual(hashlib.sha256(json.dumps(legacy, sort_keys=True).encode()).hexdigest(), packet.fingerprint)
        self.assertEqual(legacy['request'], json.loads(prompt_messages(packet)[1]['content'])['packet']['request'])
        saved = Reviews(self.store).create(self.request)
        self.assertTrue(Reviews(self.store).get(saved['review_id'], owner=OWNER)['context_current'])
        self.assertNotIn('intent', saved['original']['packet']['request'])

    def test_explicit_task_is_bounded_fingerprinted_and_saved_without_becoming_evidence(self):
        request = replace(self.request, current_message='Could you send the agenda?', intent='Thank them and ask one question.')
        packet = self.engine.prepare(request)
        self.assertNotEqual(self.engine.prepare(self.request).fingerprint, packet.fingerprint)
        self.assertEqual(self.engine.prepare(self.request).evidence, packet.evidence)
        self.assertEqual(request, DraftRequest(**packet_dict(packet)['request']))
        saved = Reviews(self.store).create(request)
        self.assertEqual(request.intent, saved['original']['packet']['request']['intent'])
        self.assertTrue(Reviews(self.store).get(saved['review_id'], owner=OWNER)['context_current'])
        for changes in ({'intent': ''}, {'current_message': ' '}, {'intent': 'x'*501},
                        {'current_message': 'x'*2001}, {'intent': True}, {'current_message': []}):
            with self.assertRaises(ValueError):
                replace(self.request, **changes)
