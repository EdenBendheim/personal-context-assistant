from copy import deepcopy
import json
from pathlib import Path
import unittest

from personal_context.generation_format import PROMPT_VERSION, TASK_PROMPT_VERSION
from personal_context.live_generation import load_study
from personal_context.local_model import LocalModelConfig, OllamaProvider
from personal_context.prompt_comparison import compare, declare


class ScriptedProvider(OllamaProvider):
    def __init__(self):
        super().__init__(LocalModelConfig('synthetic', local_only_confirmed=True, expected_digest='0'*64))
        self.requests = []

    def describe(self):
        return dict(backend='scripted', prompt_version=PROMPT_VERSION)

    def _chat(self, messages, *, schema):
        if schema is not None:
            raise AssertionError('Comparison should omit the transport schema')
        payload = json.loads(messages[1]['content'])
        self.requests.append(payload)
        if payload['prompt_version'] == PROMPT_VERSION:
            return '{"abstain_reason":"No reply", "segments":[]}'
        return '{"abstain_reason":null, "segments":[{"text":"Which test should I run?","kind":"question","support":[]}]}'


class PromptComparisonTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]/'examples/reply_quality_evaluation'
        self.inputs = load_study(root/'manifest.json')
        self.criteria = json.loads((root/'criteria.json').read_text())
        self.provider = ScriptedProvider()

    def test_held_out_comparison_shares_packets_preserves_skips_and_records_each_prompt(self):
        receipt = declare(self.inputs, self.criteria, self.provider, split='evaluation')
        self.assertFalse(self.provider.requests)
        result = compare(self.inputs, self.criteria, self.provider, receipt)
        baseline, variant = result['reports'].values()
        self.assertEqual((PROMPT_VERSION, TASK_PROMPT_VERSION), (baseline['prompt_version'], variant['prompt_version']))
        self.assertEqual((16, 16), (baseline['provider_calls'], variant['provider_calls']))
        self.assertEqual({'provider_abstained': 16, 'needs_history': 2}, baseline['statuses'])
        self.assertEqual({'needs_review': 16, 'needs_history': 2}, variant['statuses'])
        for left, right in zip(self.provider.requests[:16], self.provider.requests[16:], strict=True):
            self.assertEqual(left['packet'], right['packet'])
            self.assertEqual(left['schema'], right['schema'])

    def test_changed_criteria_or_split_refuses_calls(self):
        receipt = declare(self.inputs, self.criteria, self.provider, split='evaluation')
        altered = deepcopy(self.criteria)
        altered['cases']['rehearsal']['thanks'] = 'Changed criterion.'
        with self.assertRaisesRegex(ValueError, 'differ from the declaration'):
            compare(self.inputs, altered, self.provider, receipt)
        with self.assertRaisesRegex(ValueError, 'declared split'):
            declare(self.inputs, self.criteria, self.provider, split='development')
        self.assertFalse(self.provider.requests)
