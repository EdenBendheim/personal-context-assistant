from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from personal_context.format_comparison import compare, declare
from personal_context.generation_format import FLAT_SCHEMA, SCHEMA
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
        if schema == FLAT_SCHEMA:
            return json.dumps(dict(abstain_reason='Contradictory abstention.', segments=[
                dict(text='Thanks for the details.', kind='social', support=[])]))
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

    def test_changed_loaded_requests_or_messages_invalidate_the_original_declaration(self):
        frozen = declare(self.inputs, self.provider)
        changed_task = deepcopy(self.inputs)
        changed_task['document']['cases'][0]['request']['intent'] = 'Ask who is running the workshop.'
        changed_message = deepcopy(self.inputs)
        changed_message['messages'][0] = replace(changed_message['messages'][0], body='Different synthetic evidence.')
        for inputs in (changed_task, changed_message):
            with self.assertRaisesRegex(ValueError, 'differs from its declaration'):
                compare(inputs, self.provider, frozen)
        self.assertFalse(self.provider.calls)

    def test_flat_schema_changes_decoder_only_and_mixed_output_is_rejected(self):
        frozen = declare(self.inputs, self.provider, comparison='union')
        with self.assertRaisesRegex(ValueError, 'differs from its declaration'):
            compare(self.inputs, self.provider, frozen)
        self.assertFalse(self.provider.calls)
        result = compare(self.inputs, self.provider, frozen, comparison='union')
        arms = [self.provider.calls[start:start+9] for start in (0, 9, 18)]
        for union, flat, prompt_only in zip(*arms, strict=True):
            self.assertEqual(union[0], flat[0])
            self.assertEqual(union[0], prompt_only[0])
            self.assertEqual([SCHEMA, FLAT_SCHEMA, None], [union[1], flat[1], prompt_only[1]])
        flat = result['reports']['flat_schema']
        self.assertEqual({'rejected': 9}, flat['statuses'])
        self.assertTrue(all('Abstention requires no segments' in row['error'] for row in flat['cases']))
