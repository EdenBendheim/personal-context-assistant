"""Opt-in bounded thread neighbors of lexical hits, with unchanged source scopes."""
from copy import deepcopy
from datetime import datetime

from .memory import scope


def key(row):
    return row['source'], row['id']


class NeighborSearch:
    def __init__(self, store, *, window=1, max_gap_seconds=86400, max_candidates=128):
        if (type(window) is not int or not 1 <= window <= 2
                or type(max_gap_seconds) is not int or not 1 <= max_gap_seconds <= 604800
                or type(max_candidates) is not int or not 1 <= max_candidates <= 128):
            raise ValueError('Use neighbor window 1-2, time gap 1-604800 seconds and candidate cap 1-128')
        self.store, self.window = store, window
        self.max_gap_seconds, self.max_candidates = max_gap_seconds, max_candidates

    def describe(self):
        return dict(backend='lexical_thread_neighbors', window=self.window,
                    max_gap_seconds=self.max_gap_seconds, max_candidates=self.max_candidates,
                    ordering='All lexical seeds first; round-robin nearest neighbors in the same source/thread',
                    limitation='Neighbors can be unrelated or outdated. Their score is inherited from a lexical '
                    'seed, not evidence of relevance, factual support or reply quality.')

    def search(self, query, *, owner, contact, before, limit=5):
        if not isinstance(query, str) or type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError('Use a text query and result limit 1-128')
        owner, contact = scope(owner, contact)
        parameters = dict(owner=owner, contact=contact, before=before)
        snapshot = deepcopy(self.store._eligible(**parameters, style_only=False))
        if len(snapshot) > self.max_candidates:
            raise ValueError('Eligible history exceeds neighbor candidate cap; narrow the imported history')
        seeds = self.store.search(query, **parameters, limit=limit)
        known = {key(row): row for row in snapshot}
        for seed in seeds:
            if {field: seed[field] for field in known.get(key(seed), {})} != known.get(key(seed)):
                raise ValueError('Neighbor seed changed during retrieval')
        result = [dict(seed, retrieval_origin='lexical_seed') for seed in seeds]
        seen = {key(row) for row in result}
        queues = []
        for seed in seeds:
            thread = sorted((row for row in snapshot if (row['source'], row['thread']) ==
                             (seed['source'], seed['thread'])), key=lambda row: (row['timestamp'], row['id']))
            index = next(i for i, row in enumerate(thread) if key(row) == key(seed))
            timestamp = datetime.fromisoformat(seed['timestamp'])
            nearby = []
            for i in range(max(0, index-self.window), min(len(thread), index+self.window+1)):
                row = thread[i]
                gap = abs((datetime.fromisoformat(row['timestamp'])-timestamp).total_seconds())
                if i != index and gap <= self.max_gap_seconds:
                    nearby.append((abs(i-index), gap, row['timestamp'], row['id'], row))
            queues.append([dict(row, score=seed['score'], retrieval_origin='thread_neighbor',
                                neighbor_seed=dict(source=seed['source'], id=seed['id']))
                           for *_, row in sorted(nearby)])
        while len(result) < limit and any(queues):
            for queue in queues:
                while queue and key(queue[0]) in seen:
                    queue.pop(0)
                if queue and len(result) < limit:
                    row = queue.pop(0); seen.add(key(row)); result.append(row)
        if self.store._eligible(**parameters, style_only=False) != snapshot:
            raise ValueError('Neighbor context changed during retrieval; rebuild it')
        return result

    def style_examples(self, **parameters):
        return self.store.style_examples(**parameters)
