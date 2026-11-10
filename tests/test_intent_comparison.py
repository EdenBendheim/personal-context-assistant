from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from personal_context.generation import GeneratedProposal, GeneratedSegment
from personal_context.intent_comparison import compare, declare, variants
from personal_context.live_generation import load_study
from test_drafts import OWNER, CONTACT, BEFORE, message


class Provider:
    def __init__(self): self.calls = 0
    def describe(self): return dict(backend='scripted contract fixture, not real model evidence')
    def generate(self, packet):
        self.calls += 1
        if packet.request.intent:
            return GeneratedProposal((GeneratedSegment('Thanks! Which example would help?', 'question'),))
        return GeneratedProposal(abstain_reason='No reply goal supplied.')


class IntentComparisonTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root/'messages.jsonl').write_text(json.dumps(asdict(message()))+'\n')
        self.document = dict(version=1, kind='synthetic local reply study', messages='messages.jsonl', cases=[
            dict(id='demo', split='development', reference_fact='Demo Thursday.', request=dict(owner=OWNER,
                contact=CONTACT, before=BEFORE, query='demo', current_message='What should we show?',
                intent='Thank them and ask which example they want.'))])
        self.path = self.root/'manifest.json'
        self.path.write_text(json.dumps(self.document))

    def test_no_inference_declaration_then_paired_inputs_preserve_sources_and_reasons(self):
        inputs = load_study(self.path)
        original = deepcopy(inputs)
        provider = Provider()
        frozen = declare(inputs, provider)
        self.assertEqual(0, provider.calls)
        result = compare(inputs, provider, frozen)
        self.assertEqual(6, provider.calls)
        self.assertEqual({'provider_abstained': 3}, result['reports']['topic_only']['statuses'])
        self.assertEqual({'needs_review': 3}, result['reports']['explicit_task']['statuses'])
        self.assertTrue(all(row['topic_only_reason'] == 'No reply goal supplied.' for row in result['paired']))
        self.assertEqual(original, inputs)
        self.assertFalse(result['evaluation_cases_inspected'])
        self.assertFalse(result['reply_quality_scored'])

    def test_evaluation_cases_missing_tasks_and_changed_freeze_fail_before_inference(self):
        inputs = load_study(self.path)
        provider = Provider()
        frozen = declare(inputs, provider)
        for field in ('source_sha256', 'benchmark_sha256', 'prompt_version'):
            wrong = deepcopy(frozen)
            wrong[field] = 'changed'
            with self.assertRaises(ValueError): compare(inputs, provider, wrong)
        self.assertEqual(0, provider.calls)
        for change in ('split', 'intent'):
            wrong = deepcopy(inputs)
            if change == 'split': wrong['document']['cases'][0]['split'] = 'evaluation'
            else: wrong['document']['cases'][0]['request'].pop('intent')
            with self.assertRaises(ValueError): variants(wrong)
