from unittest.mock import patch
import unittest

from personal_context.neighbors import NeighborSearch
from personal_context.store import Store
from test_context import message, PARAMS


class NeighborTests(unittest.TestCase):
    def setUp(self):
        self.store=Store();self.addCleanup(self.store.close)

    def test_incoming_followup_without_topic_word_is_retrieved_and_traceable(self):
        self.store.ingest([message('seed',body='I can bring the equipment'),
            message('detail',body='Bring the tripod, not the camera.',author=PARAMS['contact'],
                    recipient=PARAMS['owner'],timestamp='2026-09-01T11:00:00Z')])
        search=NeighborSearch(self.store)
        result=search.search('equipment',**PARAMS)
        self.assertEqual(['seed','detail'],[r['id'] for r in result])
        self.assertEqual('thread_neighbor',result[1]['retrieval_origin'])
        self.assertEqual(dict(source='gmail',id='seed'),result[1]['neighbor_seed'])
        self.assertEqual(['seed'],[r['id'] for r in search.style_examples(**PARAMS)])
        self.assertEqual([],search.search('no match',**PARAMS))

    def test_time_pair_source_thread_and_count_boundaries_are_preserved(self):
        self.store.ingest([message('seed',body='equipment',timestamp='2026-08-01T10:00:00Z'),
            message('old',body='too far',timestamp='2026-08-03T10:00:00Z'),
            message('future',body='excluded',timestamp=PARAMS['before']),
            message('foreign',body='private',recipient='other@example.invalid',timestamp='2026-08-01T10:01:00Z'),
            message('other-source',source='discord',body='wrong provider',timestamp='2026-08-01T10:02:00Z'),
            message('other-thread',thread='other',body='wrong thread',timestamp='2026-08-01T10:03:00Z')])
        self.assertEqual(['seed'],[r['id'] for r in NeighborSearch(self.store).search('equipment',**PARAMS)])
        with self.assertRaisesRegex(ValueError,'cap'):
            NeighborSearch(self.store,max_candidates=1).search('equipment',**PARAMS)
        for changes in (dict(window=0),dict(window=True),dict(max_gap_seconds=0),dict(max_candidates=129)):
            with self.assertRaises(ValueError):NeighborSearch(self.store,**changes)

    def test_ties_deduplication_and_limit_keep_lexical_seeds_first(self):
        self.store.ingest([message('a',body='equipment A'),message('b',body='equipment B'),
                           message('c',body='a detail')])
        search=NeighborSearch(self.store,window=2)
        self.assertEqual(['a','b'],[r['id'] for r in search.search('equipment',**PARAMS,limit=2)])
        self.assertEqual(['a','b','c'],[r['id'] for r in search.search('equipment',**PARAMS,limit=5)])
        with self.assertRaises(ValueError):search.search('equipment',**PARAMS,limit=True)

    def test_mutation_between_seed_selection_and_return_refuses_whole_result(self):
        self.store.ingest([message()]);original=self.store.search
        def changing(*args,**kwargs):
            rows=original(*args,**kwargs)
            self.store.connection.execute("UPDATE messages SET body='changed'")
            return rows
        with patch.object(self.store,'search',side_effect=changing),self.assertRaisesRegex(ValueError,'changed'):
            NeighborSearch(self.store).search('demo',**PARAMS)
