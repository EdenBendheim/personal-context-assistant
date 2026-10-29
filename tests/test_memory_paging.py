import unittest
from unittest.mock import patch

from personal_context.memory_workspace import MemoryWorkspace
from personal_context.messages import Message
from personal_context.store import Store

OWNER, CONTACT = 'owner@example.invalid', 'alex@example.invalid'
AT, BEFORE = '2026-09-02T00:00:00Z', '2026-09-04T00:00:00Z'


class MemoryPagingTests(unittest.TestCase):
    def setUp(self):
        self.store = Store(); self.addCleanup(self.store.close)
        self.store.ingest([Message.from_dict(dict(id='1', source='gmail', thread='demo', author=OWNER,
            recipient=CONTACT, timestamp='2026-09-01T00:00:00Z', body='Synthetic demo Thursday'))])
        self.workspace = MemoryWorkspace(self.store, owner=OWNER)

    def create(self, index=0, at=AT):
        return self.workspace.memory.create(owner=OWNER, contact=CONTACT, kind='fact', text=f'Fact {index}',
            sources=[['gmail','1']], reason='Synthetic fixture', at=at)

    def page(self, **changes):
        return self.workspace.page(**(dict(contact=CONTACT, before=BEFORE, limit=7)|changes))

    def test_all_timestamp_tied_items_remain_reachable_after_new_item_and_old_edit(self):
        items = [self.create(i) for i in range(105)]
        ids = sorted([x['memory_id'] for x in items], reverse=True)
        first = self.page(); found = [x['memory_id'] for x in first['items']]
        self.assertEqual(ids[:7], found)
        self.create(200, at='2026-09-03T00:00:00Z')
        edited_id=ids[-1]
        self.workspace.memory.revise(edited_id, expected_revision=1, text='Revised old fact',
            sources=[['gmail','1']], reason='Update between pages', at='2026-09-03T01:00:00Z')
        cursor=first['next_cursor']; last=None
        with patch.object(self.workspace.memory, 'history', side_effect=AssertionError('unbounded history')):
            while cursor:
                last=self.page(cursor=cursor)
                found += [x['memory_id'] for x in last['items']]; cursor=last['next_cursor']
        self.assertEqual(ids, found); self.assertEqual(105, len(set(found)))
        self.assertEqual('Revised old fact', last['items'][-1]['text'])
        self.assertTrue(all('history' not in x for x in first['items']))

    def test_pages_preserve_cutoffs_withdrawals_and_source_privacy(self):
        item=self.create(); mid=item['memory_id']
        self.workspace.memory.revise(mid, expected_revision=1, text='Later version', sources=[['gmail','1']],
                                     reason='Updated', at='2026-09-05T00:00:00Z')
        row=self.page()['items'][0]
        self.assertEqual(2, row['revision']); self.assertEqual(1, row['context_revision'])
        self.workspace.memory.revoke(mid, expected_revision=2, reason='Withdrawn', at='2026-09-06T00:00:00Z')
        self.assertFalse(self.page()['items'][0]['eligible_at_cutoff'])
        another=self.create(2)
        with self.store.connection:
            self.store.connection.execute("UPDATE messages SET recipient='riley@example.invalid', body='other contact secret'")
        page=self.page();self.assertNotIn('other contact secret', str(page))
        self.assertTrue(all(not x['eligible_at_cutoff'] for x in page['items']))
        self.assertIsNone(self.workspace.get(another['memory_id'], include_history=False)['source_messages'][0]['message'])

    def test_bad_or_removed_cursors_and_limits_are_rejected_without_committing_pending_changes(self):
        item=self.create();mid=item['memory_id']
        other=MemoryWorkspace(self.store, owner='other@example.invalid')
        with self.assertRaises(ValueError): other.page(contact=CONTACT, before=BEFORE, cursor=mid)
        with self.assertRaises(ValueError): self.page(contact='riley@example.invalid', cursor=mid)
        for value in [0,101,True,'2']:
            with self.assertRaises(ValueError):self.page(limit=value)
        self.store.connection.execute("UPDATE messages SET body='pending edit'")
        self.assertFalse(self.page()['items'][0]['eligible_at_cutoff'])
        self.assertTrue(self.store.connection.in_transaction)
        self.store.connection.rollback()
        self.assertTrue(self.page()['items'][0]['eligible_at_cutoff'])
        with self.store.connection:
            self.store.connection.execute('DELETE FROM memory_sources WHERE memory_id=?',(mid,))
            self.store.connection.execute('DELETE FROM memory_revisions WHERE memory_id=?',(mid,))
            self.store.connection.execute('DELETE FROM memory_items WHERE id=?',(mid,))
        with self.assertRaisesRegex(ValueError,'reload'):self.page(cursor=mid)
        self.assertEqual(dict(items=[],next_cursor=None),self.page())
