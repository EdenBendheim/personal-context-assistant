from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from personal_context.generation import GeneratedProposal, GeneratedSegment
from personal_context.live_generation import load_study, study
from test_drafts import message, OWNER, CONTACT, BEFORE


class Provider:
    def __init__(self, fail=False): self.fail=fail; self.calls=0
    def describe(self): return dict(backend='synthetic test fixture')
    def generate(self, packet):
        self.calls+=1
        if self.fail: raise ValueError('Synthetic provider rejection')
        return GeneratedProposal((GeneratedSegment('Hello!', 'social'),))


class LiveGenerationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.doc=dict(version=1,kind='synthetic local reply study',messages='messages.jsonl',cases=[
            dict(id='known',split='development',reference_fact='Demo Thursday.',request=dict(owner=OWNER,contact=CONTACT,before=BEFORE,query='demo')),
            dict(id='empty',split='evaluation',reference_fact='No relevant factual history.',request=dict(owner=OWNER,contact='unknown@example.invalid',before=BEFORE,query='demo'))])
        from dataclasses import asdict
        (self.root/'messages.jsonl').write_text(json.dumps(asdict(message()))+'\n')
        self.path=self.root/'manifest.json';self.path.write_text(json.dumps(self.doc))

    def test_modes_provider_failures_and_no_history_are_reported_without_quality_claims(self):
        inputs=load_study(self.path)
        provider=Provider();report=study(inputs,provider,split='all')
        self.assertEqual(6,report['attempts']);self.assertEqual(4,report['provider_calls'])
        self.assertEqual({'needs_review':4,'needs_history':2},report['statuses'])
        self.assertFalse(report['reply_quality_scored']);self.assertFalse(report['sending_performed'])
        failed=study(inputs,Provider(fail=True),split='evaluation')
        self.assertEqual({'rejected':1,'needs_history':2},failed['statuses'])
        self.assertEqual(1,failed['provider_calls'])

    def test_private_participants_and_cross_split_conversations_are_refused(self):
        for change in ('participant','split'):
            d=deepcopy(self.doc)
            if change=='participant': d['cases'][0]['request']['owner']='real@private.example'
            else:d['cases'][1]['request']['contact']=CONTACT
            self.path.write_text(json.dumps(d))
            with self.assertRaises(ValueError):load_study(self.path)

    def test_abstention_reasons_and_no_history_notes_survive_the_study_report(self):
        class Abstaining(Provider):
            def generate(self, packet):
                return GeneratedProposal(abstain_reason='Need the owner to say what response they want.')
        report = study(load_study(self.path), Abstaining(), split='all')
        reason = 'Need the owner to say what response they want.'
        self.assertEqual({reason: 4}, report['abstention_reasons'])
        for row in report['cases']:
            if row['status'] == 'provider_abstained':
                self.assertEqual(reason, row['abstain_reason'])
                self.assertEqual([reason], row['review_notes'])
            else:
                self.assertNotIn('abstain_reason', row)
                self.assertIn('relevant factual history', row['review_notes'][0])
