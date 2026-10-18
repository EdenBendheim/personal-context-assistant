from dataclasses import replace
import unittest

from personal_context.drafts import CitedQuote, DraftEngine, DraftRequest
from personal_context.generation import GeneratedProposal,GeneratedSegment,generate
from personal_context.store import Store
from test_drafts import OWNER,CONTACT,BEFORE,message


class Provider:
    def __init__(self, proposal): self.proposal=proposal
    def generate(self, packet): return self.proposal


def proposal():
    return GeneratedProposal((GeneratedSegment('Hi Alex!', 'social'),
        GeneratedSegment('The demo is Thursday.', 'fact', (CitedQuote('message-1','demo Thursday'),)),
        GeneratedSegment('Would that work?', 'question')))


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.store=Store();self.addCleanup(self.store.close);self.store.ingest([message()])
        self.engine=DraftEngine(self.store);self.request=DraftRequest(OWNER,CONTACT,BEFORE,'demo')

    def test_generated_wording_retains_literal_sources_but_requires_semantic_review(self):
        result=generate(self.engine,self.request,Provider(proposal()))
        self.assertEqual('needs_review',result['status']);self.assertTrue(result['support_review_required'])
        self.assertEqual([1],result['segments'][1]['citation_labels'])
        self.assertEqual('1',result['citations'][0]['provenance']['id'])
        self.assertIn('not that generated wording follows',result['review_notes'][1])
        # A source-linked lie is not automatically entailed; it remains unapproved.
        lie=replace(proposal(),segments=(GeneratedSegment('The demo is Friday.', 'fact',(CitedQuote('message-1','demo Thursday'),)),))
        self.assertTrue(generate(self.engine,self.request,Provider(lie))['support_review_required'])

    def test_malformed_unsupported_style_only_and_oversized_proposals_fail(self):
        bad=[None,GeneratedProposal(),GeneratedProposal((), 'x'*501),GeneratedProposal(proposal().segments,'abstain'),
            GeneratedProposal((GeneratedSegment('Claim','fact'),)),GeneratedProposal((GeneratedSegment('Claim','unknown'),)),
            GeneratedProposal((GeneratedSegment('x'*2001,'social'),)),
            GeneratedProposal(tuple(GeneratedSegment('x'*1000,'social') for _ in range(7)))]
        for key,value in [('unknown','demo'),('style-1','demo'),('message-1','fabricated')]:
            bad.append(GeneratedProposal((GeneratedSegment('Claim','fact',(CitedQuote(key,value),)),)))
        bad.append(GeneratedProposal((GeneratedSegment('Claim','fact',(CitedQuote('message-1','demo'),)*2),)))
        for p in bad:
            with self.subTest(p=p),self.assertRaises(ValueError):generate(self.engine,self.request,Provider(p))

    def test_cold_start_skips_provider_and_explicit_abstention_returns_no_wording(self):
        class Never:
            def generate(self,packet):raise AssertionError('called')
        result=generate(self.engine,replace(self.request,query='unrelated'),Never())
        self.assertEqual('needs_history',result['status'])
        result=generate(self.engine,self.request,Provider(GeneratedProposal(abstain_reason='Need a confirmed date.')))
        self.assertEqual('provider_abstained',result['status']);self.assertEqual('',result['draft_text'])

    def test_provider_mutation_and_source_changes_cannot_replace_validation_snapshot(self):
        engine=self.engine
        class Mutating:
            def generate(self,packet):
                object.__setattr__(packet.evidence[0],'text','fabricated')
                return GeneratedProposal((GeneratedSegment('Claim','fact',(CitedQuote('message-1','fabricated'),)),))
        with self.assertRaisesRegex(ValueError,'literally'):generate(engine,self.request,Mutating())
        class Editing:
            def generate(self,packet):
                with engine.store.connection:engine.store.connection.execute("UPDATE messages SET body='changed demo'")
                return proposal()
        with self.assertRaisesRegex(ValueError,'Context changed'):generate(engine,self.request,Editing())
