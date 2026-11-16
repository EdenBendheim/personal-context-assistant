from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import random
import unittest

from personal_context.live_generation import load_study
from personal_context.reply_quality import prepare_reviews


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'examples/reply_intent_development'


class ReplyQualityTests(unittest.TestCase):
    def setUp(self):
        self.inputs = load_study(FIXTURE/'manifest.json')
        self.criteria = json.loads((FIXTURE/'criteria.json').read_text())
        path = ROOT/'experiments/reply-union-2026-11-13/results.json'
        self.study = json.loads(path.read_text())

    def prepare(self):
        return prepare_reviews(self.inputs, self.study, self.criteria, seed=17)

    def test_review_packet_hides_conditions_and_deduplicates_wording_within_a_case(self):
        state = random.getstate()
        packet, key = self.prepare()
        self.assertEqual(state, random.getstate())
        self.assertEqual((packet, key), self.prepare())
        self.assertEqual(27, len(key['attempts']))
        self.assertEqual(6, sum(len(case['candidates']) for case in packet['cases']))
        self.assertEqual(9, sum(attempt['candidate_id'] is not None for attempt in key['attempts']))
        text = json.dumps(packet)
        for hidden in ('prompt_only', 'flat_schema', 'personalized', 'elapsed_seconds', 'workshop_schedule'):
            self.assertNotIn(hidden, text)

    def test_shared_history_stays_within_each_contact_and_cutoff(self):
        source = self.inputs['messages'][0]
        self.inputs['messages'].append(replace(source, body='Future evidence', timestamp='2026-09-05T00:00:00.000000+00:00'))
        self.inputs['messages'].append(replace(source, body='Another contact', recipient='other@example.invalid'))
        packet, _ = self.prepare()
        self.assertEqual([2, 2, 2], [len(case['history']) for case in packet['cases']])
        self.assertNotIn('Future evidence', json.dumps(packet))
        self.assertNotIn('Another contact', json.dumps(packet))

    def test_rejects_missing_duplicate_or_foreign_attempts(self):
        original = self.study
        for change in ('missing', 'duplicate', 'wrong_fixture'):
            self.study = deepcopy(original)
            report = self.study['reports']['schema']
            if change == 'missing':
                report['cases'].pop()
            elif change == 'duplicate':
                report['cases'][1] = report['cases'][0]
            else:
                report['benchmark_sha256'] = '0'*64
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'must match the fixture'):
                self.prepare()
