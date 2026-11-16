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

    def test_expands_duplicate_ratings_and_retains_all_attempts(self):
        from personal_context.reply_quality import summarize_reviews

        packet, key = self.prepare()
        ratings = self.ratings(packet, key)
        exact_match = packet['cases'][0]['candidates'][0]['id']
        ratings['ratings'][exact_match]['support'] = 'unsupported'
        report = summarize_reviews(packet, key, ratings)
        self.assertEqual(6, report['distinct_wordings_rated'])
        self.assertEqual(27, len(report['attempts']))
        self.assertEqual(9, report['conditions']['flat_schema']['attempts'])
        self.assertEqual(2, report['conditions']['flat_schema']['rejected'])
        self.assertEqual(8, report['conditions']['schema']['provider_abstained'])
        matching = [attempt for attempt in report['attempts'] if attempt['candidate_id'] == exact_match]
        self.assertTrue(all(attempt['support'] == 'unsupported' and attempt['complete'] for attempt in matching))
        for tally in report['conditions'].values():
            self.assertEqual(tally['needs_review'], tally['supported'] + tally['unsupported'] + tally['uncertain'])
            self.assertEqual(tally['supported'], tally['supported_and_complete'])

    def test_drift_partial_labels_and_duplicate_criteria_cannot_be_summarized(self):
        from personal_context.reply_quality import summarize_reviews

        packet, key = self.prepare()
        ratings = self.ratings(packet, key)
        altered = deepcopy(packet)
        altered['cases'][0]['history'][0]['body'] = 'Changed context.'
        with self.assertRaisesRegex(ValueError, 'exact reviewer packet'):
            summarize_reviews(altered, key, ratings)
        candidate_id = next(iter(ratings['ratings']))
        missing = deepcopy(ratings)
        del missing['ratings'][candidate_id]
        with self.assertRaisesRegex(ValueError, 'every distinct'):
            summarize_reviews(packet, key, missing)
        ratings['ratings'][candidate_id]['completed'] = ['time', 'time']
        with self.assertRaisesRegex(ValueError, 'Invalid rating'):
            summarize_reviews(packet, key, ratings)

    @staticmethod
    def ratings(packet, key):
        return dict(version=1, reviewer_kind='assistant', prior_exposure=True,
            packet_sha256=key['packet_sha256'], ratings={
                candidate['id']: dict(support='supported', completed=list(case['criteria']), note='Test rating.')
                for case in packet['cases'] for candidate in case['candidates']})

    def test_held_out_packet_keeps_no_history_attempts_and_excludes_later_sources(self):
        from personal_context.generation import GeneratedProposal
        from personal_context.live_generation import study
        from personal_context.reply_quality import summarize_reviews

        class AbstainingFixture:
            def describe(self):
                return dict(backend='scripted local test')

            def generate(self, packet):
                return GeneratedProposal(abstain_reason='Scripted abstention.')

        fixture = ROOT/'examples/reply_quality_evaluation'
        inputs = load_study(fixture/'manifest.json')
        criteria = json.loads((fixture/'criteria.json').read_text())
        report = study(inputs, AbstainingFixture(), split='evaluation', neighbor_window=1)
        packet, key = prepare_reviews(inputs, report, criteria, seed=29)
        histories = {case['case_id']: [row['id'] for row in case['history']] for case in packet['cases']}
        self.assertEqual(['rehearsal-1', 'rehearsal-2', 'rehearsal-3'], histories['rehearsal'])
        self.assertEqual([], histories['donation'])
        scored = summarize_reviews(packet, key, self.ratings(packet, key))
        counts = scored['conditions']['study']
        self.assertEqual((18, 2, 16, 0), (counts['attempts'], counts['needs_history'],
            counts['provider_abstained'], counts['supported_and_complete']))
