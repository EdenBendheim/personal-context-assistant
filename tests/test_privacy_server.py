import unittest
from urllib.parse import quote

import test_review_server as fixtures
from personal_context.drafts import DraftRequest
from personal_context.memory import Memory
from personal_context.reviews import Reviews
from personal_context.store import Store

OWNER, CONTACT = fixtures.OWNER, fixtures.CONTACT


class PrivacyServerTests(unittest.TestCase):
    setUp = fixtures.ServerTests.setUp
    cleanup = fixtures.ServerTests.cleanup
    call = fixtures.ServerTests.call
    create = fixtures.ServerTests.create
    def test_http_preview_confirmation_and_full_copy_removal(self):
        rid = self.create()[1]['review_id']
        path = '/api/privacy?contact='+quote(CONTACT)
        status, plan, _ = self.call(path)
        self.assertEqual(200, status)
        self.assertEqual(1, plan['counts']['draft_reviews'])
        payload = dict(contact=CONTACT, expected_plan_sha256=plan['plan_sha256'], confirm=False)
        self.assertEqual(400, self.call('/api/privacy/remove', payload)[0])
        self.assertEqual(200, self.call('/api/reviews/'+rid)[0])
        payload['confirm'] = True
        status, receipt, _ = self.call('/api/privacy/remove', payload)
        self.assertEqual(200, status)
        self.assertEqual(plan['counts'], receipt['deleted'])
        self.assertEqual(400, self.call('/api/reviews/'+rid)[0])
        self.assertEqual([], self.call('/api/contacts')[1]['contacts'])
        self.assertEqual(0, sum(self.call(path)[1]['counts'].values()))
        store = Store(str(self.db), readonly=True)
        try:
            self.assertEqual(1, store.connection.execute('SELECT COUNT(*) FROM messages').fetchone()[0])
        finally: store.close()

    def test_owner_fixed_auth_stale_plan_and_foreign_packet_blockers(self):
        self.create()
        path = '/api/privacy?contact='+quote(CONTACT)
        self.assertEqual(401, self.call(path, headers={'Authorization':''})[0])
        plan = self.call(path)[1]
        payload = dict(contact=CONTACT, expected_plan_sha256=plan['plan_sha256'], confirm=True)
        self.assertEqual(400, self.call('/api/privacy/remove', payload | dict(owner='other'))[0])
        self.create()
        self.assertEqual(409, self.call('/api/privacy/remove', payload)[0])
        store = Store(str(self.db))
        Reviews(store).create(DraftRequest(CONTACT, OWNER, '2026-09-04T00:00:00Z', 'demo'))
        store.close()
        blocked = self.call(path)[1]
        self.assertFalse(blocked['can_apply'])
        self.assertEqual(400, self.call('/api/privacy/remove', payload | dict(expected_plan_sha256=blocked['plan_sha256']))[0])
        self.assertEqual(2, len(self.call('/api/reviews?contact='+quote(CONTACT))[1]))

    def test_contacts_with_only_saved_copies_remain_available_for_removal(self):
        self.create()
        store = Store(str(self.db))
        Memory(store).create(owner=OWNER, contact=CONTACT, kind='fact', text='demo preference',
                             sources=[('gmail', '1')], reason='synthetic')
        with store.connection:
            store.connection.execute("DELETE FROM messages WHERE id='1'")
        store.close()
        contacts = self.call('/api/contacts')[1]['contacts']
        self.assertEqual([CONTACT], [row['contact'] for row in contacts])
        self.assertEqual(0, contacts[0]['messages'])
        self.assertIsNone(contacts[0]['last_message'])
        plan = self.call('/api/privacy?contact='+quote(CONTACT))[1]
        self.assertEqual(0, plan['counts']['messages'])
        self.assertEqual(1, plan['counts']['memory_items'])
        self.assertEqual(1, plan['counts']['draft_reviews'])
