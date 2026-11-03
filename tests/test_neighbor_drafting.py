import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from personal_context.draft_cli import main
from personal_context.drafts import DraftEngine, DraftRequest
from personal_context.evidence_coverage import coverage, load_annotations
from personal_context.live_generation import load_study, study
from personal_context.neighbors import NeighborSearch
from personal_context.store import Store
from test_live_generation import Provider

ROOT=Path(__file__).resolve().parents[1]


class NeighborDraftingTests(unittest.TestCase):
    def setUp(self):
        self.inputs=load_study(ROOT/'examples/local_reply/manifest.json')
        self.annotations=load_annotations(ROOT/'examples/local_reply/coverage.json',self.inputs)

    def test_packet_coverage_and_study_expose_actual_extra_source_without_quality_score(self):
        report=coverage(self.inputs,self.annotations,split='all',neighbor_window=1)
        self.assertEqual(12,report['complete_contextual_source_cases'])
        result=study(self.inputs,Provider(),split='evaluation',neighbor_window=1)
        equipment=next(r for r in result['cases'] if r['case_id']=='hana-equipment' and r['mode']=='context')
        self.assertEqual({'hana-1','hana-2'},{r['id'] for r in equipment['retrieved_sources']})
        self.assertFalse(result['reply_quality_scored'])
        self.assertEqual('lexical_thread_neighbors',result['retrieval_configuration']['backend'])

    def test_default_packet_fingerprints_match_historical_saved_receipts(self):
        original=json.loads((ROOT/'experiments/local-inference-2026-11-01/reply-evaluation.json').read_text())
        store=Store();self.addCleanup(store.close);store.ingest(self.inputs['messages'])
        engine=DraftEngine(store)
        for case in self.inputs['document']['cases']:
            if case['split']!='evaluation':continue
            for mode in ('generic','context','personalized'):
                from dataclasses import replace
                packet=engine.prepare(replace(DraftRequest(**case['request']),mode=mode))
                row=next(r for r in original['cases'] if r['case_id']==case['id'] and r['mode']==mode)
                self.assertEqual(row['packet_sha256'],packet.fingerprint)

    def test_cli_opt_in_cites_neighbor_and_preserves_an_initialized_database(self):
        with tempfile.TemporaryDirectory() as directory:
            from personal_context.memory import Memory
            db=Path(directory)/'synthetic.sqlite';store=Store(str(db));store.ingest(self.inputs['messages']);Memory(store);store.close()
            before=db.read_bytes();output=io.StringIO()
            args=['draft','--db',str(db),'--owner','owner@example.invalid','--contact','hana@example.invalid',
                  '--before','2026-09-04T00:00:00Z','--query','equipment','--neighbor-window','1']
            with patch('sys.argv',args),contextlib.redirect_stdout(output):main()
            report=json.loads(output.getvalue())
            extra=report['packet']['evidence'][1]
            self.assertEqual('hana-2',extra['provenance']['id'])
            self.assertEqual('thread_neighbor',extra['provenance']['retrieval']['origin'])
            self.assertEqual('hana-1',extra['provenance']['retrieval']['seed']['id'])
            self.assertIn('tripod',report['draft_text'])
            self.assertEqual(before,db.read_bytes())

    def test_adapter_cannot_bypass_engine_source_checks(self):
        store=Store();self.addCleanup(store.close);store.ingest(self.inputs['messages'])
        foreign=store._eligible(owner='owner@example.invalid',contact='alex@example.invalid',before='2026-09-04T00:00:00Z',style_only=False)
        search=NeighborSearch(store)
        with patch.object(search,'search',return_value=foreign),self.assertRaisesRegex(ValueError,'boundary'):
            DraftEngine(store,retrieval=search).prepare(DraftRequest('owner@example.invalid','hana@example.invalid','2026-09-04T00:00:00Z','equipment'))
