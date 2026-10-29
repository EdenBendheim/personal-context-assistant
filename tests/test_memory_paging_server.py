import unittest

from personal_context.memory_workspace import MemoryWorkspace
from personal_context.store import Store
import test_review_server as fixture

OWNER, CONTACT = fixture.OWNER, fixture.CONTACT


class MemoryPagingServerTests(unittest.TestCase):
    setUp = fixture.ServerTests.setUp
    cleanup = fixture.ServerTests.cleanup
    call = fixture.ServerTests.call

    def seed(self, count=1, revisions=1, *, owner=OWNER, contact=CONTACT, source='1'):
        store=Store(str(self.db));memory=MemoryWorkspace(store,owner=owner).memory
        ids=[]
        try:
            for index in range(count):
                item=memory.create(owner=owner,contact=contact,kind='fact',text=f'Fact {index}',
                    sources=[['gmail',source]],reason='Fixture',at='2026-09-02T00:00:00Z')
                for revision in range(2,revisions+1):
                    item=memory.revise(item['memory_id'],expected_revision=revision-1,text=f'Revision {revision}',
                        sources=[['gmail',source]],reason='Correction',at=f'2026-09-02T00:00:{revision:02d}Z')
                ids.append(item['memory_id'])
        finally:store.close()
        return ids

    def test_memory_pages_enforce_owner_auth_limits_and_cursor_scope(self):
        ids=self.seed(3)
        foreign=self.seed(owner='other@example.invalid',contact='third@example.invalid',source='2')[0]
        route=f'/api/memory/page?contact={CONTACT}&before=2026-09-04T00:00:00Z'
        status,first,_=self.call(route+'&limit=2');self.assertEqual(200,status)
        self.assertEqual(2,len(first['items']));self.assertTrue(first['next_cursor'])
        second=self.call(route+'&limit=2&cursor='+first['next_cursor'])[1]
        self.assertEqual(set(ids),{x['memory_id'] for x in first['items']+second['items']})
        self.assertIsNone(second['next_cursor']);self.assertNotIn('history',first['items'][0])
        self.assertEqual(401,self.call(route,headers={'Authorization':'Bearer invalid'})[0])
        for suffix in ['&limit=0','&limit=101','&limit=abc','&cursor=unknown','&cursor='+foreign,
                       '&owner=other','&limit=1&limit=2']:
            self.assertEqual(400,self.call(route+suffix)[0],suffix)

    def test_current_and_history_pages_preserve_cutoff_and_revision_boundaries(self):
        mid=self.seed(revisions=3)[0]
        status,current,_=self.call(f'/api/memory/{mid}/current?before=2026-09-02T00:00:03Z')
        self.assertEqual(200,status);self.assertNotIn('history',current)
        self.assertEqual(3,current['revision']);self.assertEqual(2,current['context_revision'])
        route=f'/api/memory/{mid}/history/page'
        first=self.call(route+'?limit=2')[1]
        second=self.call(route+'?limit=2&cursor='+str(first['next_cursor']))[1]
        self.assertEqual([3,2,1],[x['revision'] for x in first['items']+second['items']])
        self.assertIsNone(second['next_cursor'])
        for query in ['?limit=abc','?limit=101','?cursor=0','?cursor=99','?cursor=True','?owner=other']:
            self.assertEqual(400,self.call(route+query)[0],query)
        self.assertEqual(401,self.call(route,headers={'Authorization':'Bearer invalid'})[0])

    def test_another_owner_and_moved_source_bodies_are_never_exposed(self):
        mid=self.seed(revisions=2)[0]
        foreign=self.seed(owner='other@example.invalid',contact='third@example.invalid',source='2')[0]
        for suffix in ['/current','/history/page']:
            status,data,_=self.call('/api/memory/'+foreign+suffix)
            self.assertEqual(400,status);self.assertNotIn('private other pair',str(data))
        store=Store(str(self.db))
        with store.connection:
            store.connection.execute("UPDATE messages SET recipient='riley@example.invalid',body='moved private body' WHERE id='1'")
        store.close()
        for suffix in ['/current','/history/page']:
            status,data,_=self.call('/api/memory/'+mid+suffix)
            self.assertEqual(200,status);self.assertNotIn('moved private body',str(data))
