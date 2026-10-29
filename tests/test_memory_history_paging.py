from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from personal_context.memory_workspace import MemoryWorkspace
from personal_context.messages import Message
from personal_context.store import Store

OWNER, CONTACT = 'owner@example.invalid', 'alex@example.invalid'


class HistoryPagingTests(unittest.TestCase):
    def setUp(self):
        self.store=Store(); self.addCleanup(self.store.close)
        self.store.ingest([Message.from_dict(dict(id='1',source='gmail',thread='demo',author=OWNER,
            recipient=CONTACT,timestamp='2026-09-01T00:00:00Z',body='Synthetic demo Thursday'))])
        self.workspace=MemoryWorkspace(self.store,owner=OWNER)
        self.tick=datetime(2026,9,2,tzinfo=timezone.utc)
        self.item=self.workspace.memory.create(owner=OWNER,contact=CONTACT,kind='fact',text='Original fact',
            sources=[['gmail','1']],reason='Reviewed',at=self.tick.isoformat())

    def revise(self):
        self.tick+=timedelta(seconds=1)
        self.item=self.workspace.memory.revise(self.item['memory_id'],expected_revision=self.item['revision'],
            text=f"Version {self.item['revision']+1}",sources=[['gmail','1']],reason='Correction',at=self.tick.isoformat())

    def page(self, **changes):
        return self.workspace.history_page(self.item['memory_id'],**(dict(limit=7)|changes))

    def test_long_history_is_reachable_while_another_revision_arrives_without_eager_reads(self):
        with patch.object(self.workspace.memory,'history',side_effect=AssertionError('eager history read')):
            for _ in range(104): self.revise()
            first=self.page();found=[x['revision'] for x in first['items']]
            self.revise()
            cursor=first['next_cursor']
            while cursor:
                page=self.page(cursor=cursor);found += [x['revision'] for x in page['items']]
                cursor=page['next_cursor']
        self.assertEqual(list(range(105,0,-1)),found)
        self.assertEqual(106,self.page()['items'][0]['revision'])

    def test_owner_and_cursor_boundaries_are_enforced(self):
        self.revise()
        other=MemoryWorkspace(self.store,owner='other@example.invalid')
        with self.assertRaises(ValueError):other.history_page(self.item['memory_id'])
        for cursor in [0,-1,True,'1',3]:
            with self.assertRaises(ValueError):self.page(cursor=cursor)
        for limit in [0,101,False,'2']:
            with self.assertRaises(ValueError):self.page(limit=limit)
        self.assertEqual([],self.page(cursor=1)['items'])

    def test_withdrawn_and_changed_sources_stay_auditable_without_other_contact_bodies(self):
        self.revise();self.tick+=timedelta(seconds=1)
        self.workspace.memory.revoke(self.item['memory_id'],expected_revision=2,reason='Withdrawn',at=self.tick.isoformat())
        page=self.page();self.assertEqual('revoked',page['items'][0]['status'])
        self.assertIsNone(page['items'][0]['text']);self.assertEqual([],page['items'][0]['sources'])
        self.assertEqual('Original fact',page['items'][-1]['text'])
        self.store.connection.execute("UPDATE messages SET recipient='riley@example.invalid',body='other contact secret'")
        changed=self.page()
        self.assertNotIn('other contact secret',str(changed))
        self.assertTrue(self.store.connection.in_transaction)
        self.assertIsNone(changed['items'][-1]['source_messages'][0]['message'])
        self.store.connection.rollback()
        self.assertTrue(self.page()['items'][-1]['source_messages'][0]['current'])
