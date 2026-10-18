from pathlib import Path
import tempfile
import unittest

from personal_context.generation import GeneratedProposal
from personal_context.reviews import Reviews
from personal_context.store import Store
from test_reviews import seed,request,OWNER,CONTACT
from test_generation import proposal,Provider
from test_drafts import message


class GeneratedReviewTests(unittest.TestCase):
    def setUp(self):
        self.store=Store();self.addCleanup(self.store.close);seed(self.store);self.reviews=Reviews(self.store)

    def test_generated_original_and_edit_need_explicit_revision_bound_support_review(self):
        review=self.reviews.create(request(),provider=Provider(proposal()));rid=review['review_id']
        self.assertEqual('generative',review['original']['generation_kind'])
        for support in ('not_rated','needs_check','unsupported'):
            with self.assertRaisesRegex(ValueError,'Review all generated'):
                self.reviews.feedback(rid,owner=OWNER,expected_revision=1,decision='usable',support=support)
        self.reviews.feedback(rid,owner=OWNER,expected_revision=1,decision='usable',support='supported')
        self.assertEqual({'supported':1},self.reviews.summary(owner=OWNER,contact=CONTACT)['support'])
        edited=self.reviews.edit(rid,owner=OWNER,expected_revision=1,text='Actually Friday?')
        self.assertEqual(review['original'],edited['original'])
        self.assertEqual(0,self.reviews.summary(owner=OWNER,contact=CONTACT)['rated_current_revisions'])
        with self.assertRaisesRegex(ValueError,'Review all generated'):
            self.reviews.feedback(rid,owner=OWNER,expected_revision=2,decision='usable')
        self.reviews.feedback(rid,owner=OWNER,expected_revision=2,decision='needs_work',support='unsupported')
        self.assertEqual(['supported','unsupported'],[f['support'] for f in self.reviews.feedback_history(rid,owner=OWNER)])
        with self.assertRaises(ValueError):self.reviews.feedback(rid,owner=OWNER,expected_revision=2,decision='usable',support=True)

    def test_abstention_and_failed_provider_save_nothing(self):
        result=self.reviews.create(request(),provider=Provider(GeneratedProposal(abstain_reason='Missing confirmed date.')))
        self.assertEqual('provider_abstained',result['status'])
        with self.assertRaises(ValueError):self.reviews.create(request(),provider=Provider(None))
        self.assertEqual([],self.reviews.list(owner=OWNER,contact=CONTACT))

    def test_inference_releases_writer_lock_and_concurrent_source_change_cannot_be_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            path=str(Path(folder)/'store.sqlite');a,b=Store(path),Store(path)
            try:
                seed(a);reviews=Reviews(a)
                class Concurrent:
                    def generate(self,packet):
                        b.ingest([message('2',body='demo updated plan')])
                        return proposal()
                with self.assertRaisesRegex(ValueError,'Context changed'):reviews.create(request(),provider=Concurrent())
                self.assertEqual([],reviews.list(owner=OWNER,contact=CONTACT))
            finally:a.close();b.close()

    def test_existing_feedback_table_migrates_without_losing_history(self):
        review=self.reviews.create(request());rid=review['review_id']
        self.store.connection.execute('ALTER TABLE draft_feedback RENAME TO saved_feedback')
        self.store.connection.execute('''CREATE TABLE draft_feedback(id TEXT PRIMARY KEY, review_id TEXT NOT NULL,
            revision INTEGER NOT NULL, decision TEXT NOT NULL,retrieval TEXT NOT NULL,style TEXT NOT NULL,
            notes TEXT NOT NULL,recorded_at TEXT NOT NULL)''');self.store.connection.commit()
        self.store.connection.execute("INSERT INTO draft_feedback VALUES(?, ?,1,'usable','useful','not_rated','old','2026-09-01T00:00:00Z')",('old',rid));self.store.connection.commit()
        reopened=Reviews(self.store)
        self.assertEqual('old',reopened.feedback_history(rid,owner=OWNER)[0]['id'])
        self.assertEqual('not_rated',reopened.feedback_history(rid,owner=OWNER)[0]['support'])
