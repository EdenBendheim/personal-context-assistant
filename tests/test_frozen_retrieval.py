from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from personal_context.frozen_retrieval import select_development, evaluate_frozen
from test_retrieval_comparison import benchmark
from test_semantic import SynonymFixture


class FrozenRetrievalTests(unittest.TestCase):
    def fixture(self):
        original = benchmark()
        evaluation = dict(original.cases[1], id='evaluation', split='evaluation')
        return replace(original, cases=original.cases+(evaluation,))

    def test_selection_never_runs_evaluation_and_locked_settings_are_used(self):
        provider = SynonymFixture()
        fixture = self.fixture()
        from personal_context.retrieval_comparison import compare_retrieval
        with patch('personal_context.frozen_retrieval.compare_retrieval', wraps=compare_retrieval) as compare:
            frozen = select_development(fixture, provider)
            self.assertEqual(4, compare.call_count)
            self.assertTrue(all(c.kwargs['split'] == 'development' for c in compare.call_args_list))
        self.assertFalse(frozen['evaluation_inspected'])
        self.assertEqual(.8, frozen['selected_threshold'])  # same perfect scores; highest threshold wins
        report = evaluate_frozen(fixture, provider, frozen)
        self.assertEqual('evaluation', report['split'])
        self.assertEqual(.8, report['embedding_configuration']['min_score'])
        self.assertEqual(frozen['freeze_sha256'], report['development_freeze_sha256'])

    def test_changed_receipt_benchmark_provider_or_source_refuses_before_encoding(self):
        fixture, provider = self.fixture(), SynonymFixture()
        frozen = select_development(fixture, provider)
        calls = len(provider.calls)
        altered = deepcopy(frozen)
        altered['selected_threshold'] = -.5
        with self.assertRaisesRegex(ValueError, 'receipt'):
            evaluate_frozen(fixture, provider, altered)
        with self.assertRaisesRegex(ValueError, 'changed'):
            evaluate_frozen(replace(fixture, fingerprint='different'), provider, frozen)
        with patch.object(provider, 'describe', return_value={'model': 'different'}), self.assertRaisesRegex(ValueError, 'changed'):
            evaluate_frozen(fixture, provider, frozen)
        with patch('personal_context.frozen_retrieval.source_fingerprint', return_value='different'), self.assertRaisesRegex(ValueError, 'changed'):
            evaluate_frozen(fixture, provider, frozen)
        self.assertEqual(calls, len(provider.calls))
        for thresholds in ((), (.2, .2), (float('nan'),), (1.1,)):
            with self.assertRaises(ValueError):
                select_development(fixture, provider, thresholds=thresholds)
