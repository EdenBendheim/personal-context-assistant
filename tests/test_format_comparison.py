from copy import deepcopy
import json
from pathlib import Path
import unittest

from personal_context.format_comparison import compare, declare
from personal_context.generation_format import SCHEMA
from personal_context.live_generation import load_study
from personal_context.local_model import LocalModelConfig, OllamaProvider


class ScriptedOllama(OllamaProvider):
    def __init__(self):
        super().__init__(LocalModelConfig('test-model', local_only_confirmed=True, expected_digest='0'*64))
        self.calls = []

    def describe(self):
        return dict(backend='scripted synthetic fixture')

    def _chat(self, messages, *, schema):
        self.calls.append((messages, schema))
        if schema is not None:
            return '{"segments": [], "abstain_reason": "Scripted abstention."}'
        if len(self.calls) % 2 == 0:
            return 'Thanks! Where is the file?'
        return json.dumps(dict(abstain_reason=None, segments=[dict(
            text='It starts at noon.', kind='fact',
            support=[dict(evidence_key='invented', quote='It starts at noon.')])]))


class FormatComparisonTests(unittest.TestCase):
    def setUp(self):
        fixture = Path(__file__).resolve().parents[1]/'examples/reply_intent_development/manifest.json'
        self.inputs = load_study(fixture)
        self.provider = ScriptedOllama()

    def test_only_decoder_constraint_changes_and_both_arms_validate(self):
        frozen = declare(self.inputs, self.provider)
        self.assertFalse(self.provider.calls)
        result = compare(self.inputs, self.provider, frozen)
        constrained, prompt_only = self.provider.calls[:9], self.provider.calls[9:]
        for (left, schema), (right, omitted) in zip(constrained, prompt_only, strict=True):
            self.assertEqual(left, right)
            self.assertEqual(schema, SCHEMA)
            self.assertIsNone(omitted)
        reports = result['reports']
        self.assertEqual({'provider_abstained': 9}, reports['schema']['statuses'])
        self.assertEqual({'rejected': 9}, reports['prompt_only']['statuses'])
        errors = {row['error'] for row in reports['prompt_only']['cases']}
        self.assertEqual({'Generated response is not strict proposal JSON',
                          'Generated support must quote available factual evidence literally'}, errors)
        self.assertFalse(result['sending_performed'])

    def test_changed_declaration_and_evaluation_cases_fail_before_model_calls(self):
        frozen = declare(self.inputs, self.provider)
        with self.assertRaisesRegex(ValueError, 'differs from its declaration'):
            compare(self.inputs, self.provider, frozen | {'source_sha256': 'changed'})
        for field in ('split', 'intent'):
            inputs = deepcopy(self.inputs)
            case = inputs['document']['cases'][0]
            if field == 'split':
                case['split'] = 'evaluation'
            else:
                case['request'].pop(field)
            with self.assertRaisesRegex(ValueError, 'development-only'):
                declare(inputs, self.provider)
        self.assertFalse(self.provider.calls)
