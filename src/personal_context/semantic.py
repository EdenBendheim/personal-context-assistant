"""Opt-in dense retrieval with the lexical store's participant/time boundaries."""
from copy import deepcopy
import math

from .embeddings import embed_validated, cosine
from .memory import scope


class EmbeddingSearch:
    def __init__(self, store, provider, *, min_score=.2, max_candidates=128):
        if (type(min_score) not in (int, float) or not math.isfinite(min_score)
                or not -1 <= min_score <= 1 or type(max_candidates) is not int
                or not 1 <= max_candidates <= 128):
            raise ValueError('Use cosine threshold -1 to 1 and candidate cap 1-128')
        self.store, self.provider = store, provider
        self.min_score, self.max_candidates = float(min_score), max_candidates

    def describe(self):
        return dict(backend='embedding_cosine', provider=deepcopy(self.provider.describe()),
                    min_score=self.min_score, max_candidates=self.max_candidates,
                    cache='none', limitation='Cosine similarity is not factual support or measured reply quality')

    def search(self, query, *, owner, contact, before, limit=5):
        if not isinstance(query, str) or type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError('Use a text query and result limit 1-128')
        owner, contact = scope(owner, contact)
        parameters = dict(owner=owner, contact=contact, before=before, style_only=False)
        candidates = self.store._eligible(**parameters)
        if not query.strip() or not candidates:
            return []
        if len(candidates) > self.max_candidates:
            raise ValueError('Eligible history exceeds embedding candidate cap; narrow the imported history')
        snapshot = deepcopy(candidates)
        # Filter before encoding: another contact's or future text must never
        # enter even a local model request, rather than just being hidden later.
        vectors = embed_validated(self.provider, [query, *(row['body'] for row in snapshot)])
        if self.store._eligible(**parameters) != snapshot:
            raise ValueError('Embedding context changed during encoding; rebuild retrieval')
        scored = [(row, cosine(vectors[0], vector)) for row, vector in zip(snapshot, vectors[1:])]
        ranked = sorted((row | dict(score=round(score, 6)) for row, score in scored if score >= self.min_score),
                        key=lambda row: (-row['score'], row['timestamp'], row['source'], row['id']))
        return ranked[:limit]

    def style_examples(self, **parameters):
        # Preserve the explicit outbound-only style contract unchanged.
        return self.store.style_examples(**parameters)
