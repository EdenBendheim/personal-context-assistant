"""Bounded synthetic reply study with real-provider failures retained for review."""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
from time import perf_counter

from .drafts import DraftEngine, DraftRequest
from .generation import generate
from .generation_format import PROMPT_VERSION
from .messages import Message
from .model_options import add_model_options, configured_provider
from .store import Store
from .retrieval_options import add_retrieval_options, retrieval_for, description

MODES = ('generic', 'context', 'personalized')


def load_study(path):
    path = Path(path)
    raw = path.read_bytes()
    fixture = (path.parent/'messages.jsonl').read_bytes()
    if len(raw) > 200_000 or len(fixture) > 200_000:
        raise ValueError('Synthetic reply inputs exceed 200,000 bytes')
    doc = json.loads(raw)
    if (not isinstance(doc, dict) or doc.get('version') != 1 or type(doc.get('version')) is not int
            or doc.get('kind') != 'synthetic local reply study' or doc.get('messages') != 'messages.jsonl'
            or not isinstance(doc.get('cases'), list) or not 1 <= len(doc['cases']) <= 12):
        raise ValueError('Invalid bounded synthetic reply study')
    messages = [Message.from_dict(json.loads(line)) for line in fixture.decode().splitlines() if line.strip()]
    if any(not p.endswith('@example.invalid') for m in messages for p in (m.author, m.recipient)):
        raise ValueError('Study fixtures must use invented example.invalid participants')
    ids, scopes = set(), {}
    for case in doc['cases']:
        if (not isinstance(case, dict) or not isinstance(case.get('id'), str) or not 1 <= len(case['id']) <= 80 or case['id'] in ids
                or case.get('split') not in ('development', 'evaluation')
                or not isinstance(case.get('reference_fact'), str) or not 1 <= len(case['reference_fact']) <= 500):
            raise ValueError('Invalid synthetic reply case')
        ids.add(case['id'])
        request = DraftRequest(**case['request'])
        if not all(p.endswith('@example.invalid') for p in (request.owner, request.contact)):
            raise ValueError('Study requests must use invented participants')
        pair = (request.owner, request.contact)
        if pair in scopes and scopes[pair] != case['split']:
            raise ValueError('Development and evaluation conversations must be disjoint')
        scopes[pair] = case['split']
    return dict(document=doc, messages=messages, fingerprint=hashlib.sha256(raw+b'\0'+fixture).hexdigest())


class CountingProvider:
    def __init__(self, provider):
        self.provider, self.calls = provider, 0
    def describe(self):
        return self.provider.describe()
    def generate(self, packet):
        self.calls += 1
        return self.provider.generate(packet)


def study(study_inputs, provider, *, split='development', neighbor_window=0):
    if split not in ('development', 'evaluation', 'all'):
        raise ValueError('Choose a declared study split')
    configuration = deepcopy(provider.describe())
    retrieval_configuration = description(neighbor_window)
    rows = []
    for case in study_inputs['document']['cases']:
        if split != 'all' and case['split'] != split:
            continue
        request = DraftRequest(**case['request'])
        for mode in MODES:
            store = Store()
            counted = CountingProvider(provider)
            retrieved_sources = []
            started = perf_counter()
            try:
                store.ingest(study_inputs['messages'])
                engine = DraftEngine(store, retrieval=retrieval_for(store, neighbor_window))
                selected = replace(request, mode=mode)
                packet = engine.prepare(selected)
                retrieved_sources = [dict(source=e.provenance['source'], id=e.provenance['id'])
                                     for e in packet.evidence if e.kind == 'message']
                result = generate(engine, selected, counted)
                row = {k: result[k] for k in ('status', 'draft_text', 'packet_sha256', 'citations', 'segments',
                                             'support_review_required') if k in result}
            except ValueError as exc:
                row = dict(status='rejected', draft_text='', error=str(exc))
            finally:
                store.close()
            rows.append(dict(case_id=case['id'], split=case['split'], mode=mode,
                reference_fact_for_human_review=case['reference_fact'], provider_calls=counted.calls,
                elapsed_seconds=perf_counter()-started, retrieved_sources=retrieved_sources, **row))
    if not rows:
        raise ValueError('The selected reply split has no cases')
    if configuration != provider.describe():
        raise ValueError('Provider configuration changed during reply study')
    return dict(version=1, kind='synthetic provider reply study', benchmark_sha256=study_inputs['fingerprint'],
        prompt_version=PROMPT_VERSION, split=split, configuration=configuration,
        retrieval_configuration=retrieval_configuration, modes=list(MODES),
        attempts=len(rows), provider_calls=sum(r['provider_calls'] for r in rows),
        statuses=dict(Counter(r['status'] for r in rows)), cases=rows,
        reply_quality_scored=False, semantic_entailment_automated=False, sending_performed=False,
        limitation='Generated text and literal citation checks require human review. Provider rejection/abstention '
                   'is retained, not hidden. Timing includes model loading and local infrastructure. '
                   'Synthetic examples do not establish owner-style imitation or real-user preference.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--split', choices=('development', 'evaluation', 'all'), default='development')
    add_model_options(parser)
    add_retrieval_options(parser)
    args = parser.parse_args()
    try:
        inputs = load_study(args.manifest)
        if not args.local_model or not args.expected_model_digest:
            raise ValueError('Live reply study requires an explicit local model and expected digest')
        result = study(inputs, configured_provider(args), split=args.split, neighbor_window=args.neighbor_window)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f'Local reply study failed: {exc}\n')
    print(json.dumps(result, indent=2, allow_nan=False))
    if result['statuses'].get('rejected'):
        parser.exit(1)


if __name__ == '__main__':
    main()
