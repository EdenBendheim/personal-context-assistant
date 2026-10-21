import math
import unittest

from personal_context.embeddings import embed_validated, normalize_vectors, cosine


class EmbeddingContractTests(unittest.TestCase):
    def test_normalized_cosine_count_and_input_isolation(self):
        texts = ['meeting', 'appointment']
        class Provider:
            def embed(self, values):
                values.clear()
                return [[3, 4], [6, 8]]
        vectors = embed_validated(Provider(), texts)
        self.assertEqual(['meeting', 'appointment'], texts)
        self.assertEqual(((.6, .8), (.6, .8)), vectors)
        self.assertEqual(1., cosine(*vectors))
        self.assertEqual(0., cosine((1., 0.), (0., 1.)))
        self.assertEqual(-1., cosine((1., 0.), (-1., 0.)))

    def test_invalid_text_is_rejected_before_provider_and_bad_vectors_fail(self):
        class Uncalled:
            def embed(self, values):
                raise AssertionError('provider must not run')
        for texts in ([], [''], ['a']*130, ['é'*2049], ['a'*4096]*65, [3]):
            with self.subTest(texts=str(texts)[:30]), self.assertRaises(ValueError):
                embed_validated(Uncalled(), texts)
        for vectors in ([], [[0, 0]], [[True, 1]], [[float('nan')]], [[float('inf')]],
                        [[10**1000]], [[]], [[1]*4097], [[1], [1, 2]], [['1']]):
            with self.subTest(vectors=str(vectors)[:30]), self.assertRaises(ValueError):
                normalize_vectors(vectors, max(1, len(vectors)))
        with self.assertRaises(ValueError):
            normalize_vectors([[1]], 2)
        self.assertTrue(all(math.isfinite(v) for v in normalize_vectors([[1e300, 1e300]], 1)[0]))
