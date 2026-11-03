from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from personal_context.evidence_coverage import coverage, load_annotations
from personal_context.live_generation import load_study

ROOT = Path(__file__).resolve().parents[1]


class EvidenceCoverageTests(unittest.TestCase):
    def setUp(self):
        self.inputs = load_study(ROOT/'examples/local_reply/manifest.json')
        self.path = ROOT/'examples/local_reply/coverage.json'

    def test_original_equipment_failure_is_visible_without_scoring_replies(self):
        annotations = load_annotations(self.path, self.inputs)
        report = coverage(self.inputs, annotations, split='all')
        self.assertEqual(24, len(report['cases']))
        self.assertEqual(12, report['contextual_source_cases'])
        self.assertEqual(10, report['complete_contextual_source_cases'])
        equipment = [r for r in report['cases'] if r['case_id'] == 'hana-equipment' and r['mode'] != 'generic']
        self.assertTrue(all(r['missing'] == [('synthetic', 'hana-2')] for r in equipment))
        self.assertNotIn('Bring the tripod', json.dumps(report))
        self.assertIsNone(next(r for r in report['cases'] if r['case_id'] == 'ivy-invoice')['required_source_recall'])

    def test_changed_fixture_foreign_future_duplicate_or_missing_labels_are_refused(self):
        original = json.loads(self.path.read_text())
        bad = []
        for value in ([dict(source='synthetic', id='ivy-2')], [dict(source='synthetic', id='alex-2')],
                      [dict(source='synthetic', id='absent')], [dict(source='synthetic', id='hana-2')]*2):
            d = deepcopy(original); d['required_sources']['hana-equipment'] = value; bad.append(d)
        d = deepcopy(original); d['study_sha256'] = 'changed'; bad.append(d)
        d = deepcopy(original); del d['required_sources']['hana-equipment']; bad.append(d)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'labels.json'
            for doc in bad:
                path.write_text(json.dumps(doc))
                with self.assertRaises(ValueError): load_annotations(path, self.inputs)
