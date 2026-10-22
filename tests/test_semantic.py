import unittest

from personal_context.semantic import EmbeddingSearch
from personal_context.store import Store
from test_context import message, PARAMS


class SynonymFixture:
    """Handwritten vectors, not a trained embedding model."""
    def __init__(self):
        self.calls = []
    def describe(self):
        return dict(kind='scripted-synthetic-vectors')
    def embed(self, texts):
        self.calls.append(list(texts))
        return [[1., 0.] if any(word in text.lower() for word in ('meeting', 'appointment'))
                else [0., 1.] for text in texts]


class SemanticSearchTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.addCleanup(self.store.close)
        self.provider = SynonymFixture()
        self.search = EmbeddingSearch(self.store, self.provider)

    def test_synonym_fixture_retains_sources_and_filters_before_any_encoding(self):
        self.store.ingest([message(body='The appointment is Thursday'),
            message('2', body='A meeting tomorrow', recipient='other@example.invalid'),
            message('3', body='The meeting is Friday', timestamp=PARAMS['before']),
            message('4', body='The other appointment', author=PARAMS['contact'], recipient=PARAMS['owner']),
            message('5', body='Lunch is pizza')])
        self.assertEqual([], self.store.search('meeting', **PARAMS))
        result = self.search.search('meeting', **PARAMS)
        self.assertEqual(['1', '4'], [row['id'] for row in result])
        self.assertEqual('gmail', result[0]['source'])
        self.assertEqual('thread-1', result[0]['thread'])
        self.assertEqual(1., result[0]['score'])
        self.assertEqual(['meeting', 'The appointment is Thursday', 'The other appointment', 'Lunch is pizza'], self.provider.calls[0])
        self.assertEqual(['1', '5'], [r['id'] for r in self.search.style_examples(**PARAMS)])

    def test_source_mutation_during_encoding_invalidates_the_whole_result(self):
        self.store.ingest([message()])
        outer = self
        class Mutating(SynonymFixture):
            def embed(self, texts):
                outer.store.connection.execute("UPDATE messages SET body='changed'")
                return super().embed(texts)
        with self.assertRaisesRegex(ValueError, 'changed during'):
            EmbeddingSearch(self.store, Mutating()).search('meeting', **PARAMS)

    def test_empty_history_bounds_threshold_and_stable_ties(self):
        self.assertEqual([], self.search.search('meeting', **PARAMS))
        self.assertEqual([], self.provider.calls)
        self.store.ingest([message('z', body='appointment one'), message('a', body='appointment two')])
        self.assertEqual(['a'], [r['id'] for r in self.search.search('meeting', **PARAMS, limit=1)])
        self.assertEqual([], self.search.search('   ', **PARAMS))
        self.provider.calls.clear()
        with self.assertRaisesRegex(ValueError, 'candidate cap'):
            EmbeddingSearch(self.store, self.provider, max_candidates=1).search('meeting', **PARAMS)
        self.assertEqual([], self.provider.calls)
        for options in (dict(min_score=float('nan')), dict(min_score=True), dict(min_score=2),
                        dict(max_candidates=0), dict(max_candidates=129)):
            with self.assertRaises(ValueError):
                EmbeddingSearch(self.store, self.provider, **options)
        for limit in (True, 0, 129):
            with self.assertRaises(ValueError):
                self.search.search('meeting', **PARAMS, limit=limit)
