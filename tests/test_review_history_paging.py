import unittest

from personal_context.reviews import Reviews
from personal_context.store import Store
from test_reviews import OWNER, CONTACT, seed, request


class ReviewHistoryPagingTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.addCleanup(self.store.close)
        seed(self.store)
        self.reviews = Reviews(self.store)
        self.rid = self.reviews.create(request())['review_id']

    def test_immutable_cursor_reaches_all_old_revisions_while_a_new_edit_arrives(self):
        for revision in range(1, 105):
            self.reviews.edit(self.rid, owner=OWNER, expected_revision=revision, text=f'Wording {revision+1}')
        page = self.reviews.history_page(self.rid, owner=OWNER.upper(), limit=13)
        self.reviews.edit(self.rid, owner=OWNER, expected_revision=105, text='Arrived while browsing')
        items = list(page['items'])
        while page['next_cursor'] is not None:
            page = self.reviews.history_page(self.rid, owner=OWNER, limit=13, cursor=page['next_cursor'])
            items.extend(page['items'])
        self.assertEqual(list(range(105, 0, -1)), [i['revision'] for i in items])
        self.assertEqual(106, self.reviews.history_page(self.rid, owner=OWNER)['items'][0]['revision'])
        self.assertFalse(self.store.connection.in_transaction)

    def test_invalid_scope_and_cursors_preserve_pending_writes(self):
        for changes in (dict(limit=0), dict(limit=101), dict(limit=True), dict(cursor=True),
                        dict(cursor=0), dict(cursor=99), dict(owner='other@example.invalid')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.reviews.history_page(self.rid, **(dict(owner=OWNER) | changes))
        self.store.connection.execute("UPDATE messages SET body = 'pending' WHERE id = '1'")
        self.reviews.history_page(self.rid, owner=OWNER)
        self.assertTrue(self.store.connection.in_transaction)
        self.store.connection.rollback()
        self.assertEqual('demo Thursday :D', self.store.connection.execute('SELECT body FROM messages').fetchone()[0])
