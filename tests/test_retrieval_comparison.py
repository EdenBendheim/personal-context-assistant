from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from personal_context.evaluation import Benchmark, load_benchmark
from personal_context.retrieval_comparison import compare_retrieval, main
from test_context import message, PARAMS
from test_semantic import SynonymFixture


def benchmark():
    messages = (message('1', body='The appointment is Thursday'),
                message('2', body='The coffee is ready', author=PARAMS['contact'], recipient=PARAMS['owner']),
                message('future', body='meeting', timestamp='2026-10-01T00:00:00Z'),
                message('wrong-contact', body='meeting', recipient='elsewhere@example.invalid'))
    cases = tuple(dict(id=query, split='development', thread='thread-1', **PARAMS, limit=5, query=query,
        relevant=[dict(source='gmail', id='1')], style_relevant=[dict(source='gmail', id='1')],
        forbidden=[dict(source='gmail', id='future'), dict(source='gmail', id='wrong-contact')])
        for query in ('meeting', 'appointment'))
    return Benchmark(messages, cases, 'handwritten-synthetic-fixture')


class RetrievalComparisonTests(unittest.TestCase):
    def test_paired_metrics_use_identical_cases_and_do_not_expose_text(self):
        provider = SynonymFixture()
        report = compare_retrieval(benchmark(), provider)
        self.assertEqual(.5, report['lexical']['macro_recall'])
        self.assertEqual(1., report['embedding']['macro_recall'])
        self.assertEqual(.5, report['embedding_minus_lexical']['macro_recall'])
        self.assertFalse(report['passed'])  # lexical's synonym miss remains visible
        for key in ('lexical', 'embedding'):
            self.assertEqual(0, report[key]['boundary_violations'])
            self.assertEqual(['meeting', 'appointment'], [case['id'] for case in report[key]['cases']])
            self.assertEqual(report['benchmark_sha256'], report[key]['benchmark_sha256'])
        self.assertNotIn('The appointment is Thursday', json.dumps(report))
        self.assertEqual('none', report['embedding_configuration']['cache'])
        self.assertEqual(2, len(provider.calls))

    def test_worse_embedding_precision_and_configuration_changes_are_visible(self):
        class Indiscriminate(SynonymFixture):
            def embed(self, texts): return [[1, 0] for _ in texts]
        fixture = benchmark()
        report = compare_retrieval(replace(fixture, cases=(fixture.cases[1],)), Indiscriminate())
        self.assertLess(report['embedding_minus_lexical']['macro_precision'], 0)
        self.assertFalse(report['embedding']['passed'])
        class Changing(SynonymFixture):
            def describe(self): return dict(call_count=len(self.calls))
        with self.assertRaisesRegex(ValueError, 'configuration changed'):
            compare_retrieval(benchmark(), Changing())

    def test_cli_fixed_manifest_reports_failed_scores_and_unconfirmed_refusal(self):
        path = Path(__file__).resolve().parents[1] / 'examples/benchmark/manifest.json'
        args = ['compare', str(path), '--model', 'synthetic-fixture', '--confirm-local-only']
        output = StringIO()
        with patch('sys.argv', args), patch('personal_context.retrieval_comparison.provider_from_arguments',
                return_value=SynonymFixture()), redirect_stdout(output), self.assertRaises(SystemExit) as caught:
            main()
        self.assertEqual(1, caught.exception.code)
        report = json.loads(output.getvalue())
        self.assertEqual(load_benchmark(path).fingerprint, report['benchmark_sha256'])
        self.assertEqual('development', report['split'])
        self.assertEqual(6, report['lexical']['case_count'])
        with patch('sys.argv', args[:-1]), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
            main()
        self.assertEqual(2, caught.exception.code)
