from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from personal_context.generation_evaluation import evaluate_generation
from personal_context.generation import generate

FIXTURE=Path(__file__).resolve().parents[1]/'examples/drafting/manifest.json'


class GenerationEvaluationTests(unittest.TestCase):
    def test_fixed_scripted_cases_keep_semantic_gaps_explicit_and_omit_private_bodies(self):
        result=evaluate_generation(FIXTURE)
        self.assertEqual(13,result['case_count']);self.assertEqual(13,result['passed']);self.assertEqual(0,result['failed'])
        self.assertFalse(result['model_inference_performed'])
        self.assertEqual(2,result['contradicted_fixture_wordings_requiring_human_review'])
        self.assertNotIn('demo Thursday',json.dumps(result))
        self.assertEqual(result['benchmark_sha256'],evaluate_generation(FIXTURE)['benchmark_sha256'])

    def test_runner_detects_disabled_review_gate(self):
        def broken(engine,request,provider):
            result=generate(engine,request,provider)
            if result['status']=='needs_review':result['support_review_required']=False
            return result
        with patch('personal_context.generation_evaluation.generate',side_effect=broken):
            self.assertGreater(evaluate_generation(FIXTURE)['failed'],0)

    def test_mutated_manifest_identity_and_duplicate_cases_are_rejected(self):
        manifest=json.loads(FIXTURE.read_text())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'manifest.json';(path.parent/'messages.jsonl').write_bytes((FIXTURE.parent/'messages.jsonl').read_bytes())
            for data in (manifest|dict(version=True),manifest|dict(messages='../elsewhere'),
                         manifest|dict(cases=manifest['cases']*2)):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):evaluate_generation(path)
