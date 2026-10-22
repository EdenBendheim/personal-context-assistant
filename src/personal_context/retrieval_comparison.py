"""Paired lexical/embedding evaluation on identical fixed synthetic cases."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from .embedding_cli import add_embedding_arguments, provider_from_arguments
from .evaluation import evaluate, load_benchmark
from .semantic import EmbeddingSearch
from .store import Store


def compare_retrieval(benchmark, provider, *, split='development', min_score=.2, max_candidates=128):
    store = Store()
    try:
        store.ingest(benchmark.messages)
        retriever = EmbeddingSearch(store, provider, min_score=min_score, max_candidates=max_candidates)
        configuration = deepcopy(retriever.describe())
        lexical = evaluate(benchmark, split=split, store=store)
        embedding = evaluate(benchmark, split=split, store=retriever)
        if configuration != retriever.describe():
            raise ValueError('Embedding configuration changed during comparison')
        deltas = {}
        for metric in ('macro_recall', 'macro_precision', 'boundary_violations'):
            a, b = lexical[metric], embedding[metric]
            deltas[metric] = b - a if a is not None and b is not None else None
        return dict(version=1, benchmark_sha256=benchmark.fingerprint, split=split,
                    embedding_configuration=configuration, lexical=lexical, embedding=embedding,
                    embedding_minus_lexical=deltas, passed=lexical['passed'] and embedding['passed'],
                    limitation='Fixed synthetic retrieval only; not learned-model validation, reply quality or factual entailment')
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--split', choices=('development', 'evaluation', 'all'), default='development')
    add_embedding_arguments(parser)
    args = parser.parse_args()
    try:
        report = compare_retrieval(load_benchmark(args.manifest), provider_from_arguments(args),
            split=args.split, min_score=args.min_score, max_candidates=args.max_candidates)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'Retrieval comparison failed: {exc}\n')
    print(json.dumps(report, indent=2))
    if not report['passed']: parser.exit(1)


if __name__ == '__main__': main()
