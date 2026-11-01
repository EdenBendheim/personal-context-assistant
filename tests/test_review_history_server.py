import unittest

from personal_context.reviews import Reviews
from personal_context.store import Store
from test_reviews import request, OWNER
import test_review_server as fixture


class ReviewHistoryServerTests(unittest.TestCase):
    setUp = fixture.ServerTests.setUp
    cleanup = fixture.ServerTests.cleanup
    call = fixture.ServerTests.call

    def prepare(self):
        store = Store(str(self.db))
        try:
            reviews = Reviews(store)
            rid = reviews.create(request())['review_id']
            for revision in (1, 2):
                reviews.feedback(rid, owner=OWNER, expected_revision=revision, decision='needs_work', notes=f'Note {revision}')
                reviews.edit(rid, owner=OWNER, expected_revision=revision, text=f'Edited {revision+1}')
            reviews.feedback(rid, owner=OWNER, expected_revision=3, decision='needs_work')
            other = reviews.create(request(owner='other@example.invalid', contact='third@example.invalid', query='private'))['review_id']
            return rid, other
        finally:
            store.close()

    def test_current_inspection_does_not_eagerly_return_history_or_feedback(self):
        rid, other = self.prepare()
        status, current, headers = self.call(f'/api/reviews/{rid}/current')
        self.assertEqual(200, status)
        self.assertEqual(3, current['revision'])
        self.assertNotIn('feedback', current)
        self.assertNotIn('history', current)
        self.assertEqual('no-store', headers['Cache-Control'])
        for suffix in ['/current', '/history/page', '/feedback/page']:
            self.assertEqual(400, self.call(f'/api/reviews/{other}{suffix}')[0])
            self.assertEqual(401, self.call(f'/api/reviews/{rid}{suffix}', headers={'Authorization':'Bearer invalid'})[0])

    def test_both_pagers_are_complete_and_reject_malformed_or_forged_parameters(self):
        rid, _ = self.prepare()
        for kind in ('history', 'feedback'):
            route = f'/api/reviews/{rid}/{kind}/page'
            first = self.call(route+'?limit=2')[1]
            second = self.call(route+'?limit=2&cursor='+str(first['next_cursor']))[1]
            self.assertEqual([3, 2, 1], [i['revision'] for i in first['items']+second['items']])
            self.assertIsNone(second['next_cursor'])
            for bad in ['?limit=0', '?limit=101', '?limit=abc', '?limit=1&limit=2', '?owner=other', '?cursor=unknown']:
                self.assertEqual(400, self.call(route+bad)[0], (kind, bad))
        self.assertEqual(400, self.call(f'/api/reviews/{rid}/current?owner=other')[0])
