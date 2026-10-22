"""Opt-in embedding search of an existing local store, opened read-only."""
import argparse
import json
import sqlite3

from .local_embeddings import LocalEmbeddingConfig, OllamaEmbeddingProvider
from .semantic import EmbeddingSearch
from .store import Store


def add_embedding_arguments(parser):
    parser.add_argument('--model', required=True, help='Name of an already installed local embedding model')
    parser.add_argument('--endpoint', default='http://127.0.0.1:11434')
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--confirm-local-only', action='store_true',
                        help='Confirm the local Ollama daemon has cloud disabled')
    parser.add_argument('--min-score', type=float, default=.2, help='Untuned cosine threshold, not a probability')
    parser.add_argument('--max-candidates', type=int, default=128)


def provider_from_arguments(args):
    return OllamaEmbeddingProvider(LocalEmbeddingConfig(args.model, endpoint=args.endpoint,
        timeout=args.timeout, local_only_confirmed=args.confirm_local_only))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query')
    parser.add_argument('--db', required=True)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--contact', required=True)
    parser.add_argument('--before', required=True, help='Exclusive timestamp cutoff')
    parser.add_argument('--limit', type=int, default=5)
    add_embedding_arguments(parser)
    args = parser.parse_args()
    store = None
    try:
        provider = provider_from_arguments(args)
        store = Store(args.db, readonly=True)
        search = EmbeddingSearch(store, provider, min_score=args.min_score, max_candidates=args.max_candidates)
        results = search.search(args.query, owner=args.owner, contact=args.contact, before=args.before, limit=args.limit)
        report = dict(retrieval=search.describe(), results=results)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, f'Embedding search failed: {exc}\n')
    finally:
        if store is not None: store.close()
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
