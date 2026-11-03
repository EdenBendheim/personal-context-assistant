"""Audit labeled source availability separately from generated reply quality."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from .drafts import DraftEngine, DraftRequest
from .live_generation import load_study, MODES
from .store import Store


def load_annotations(path, inputs):
    raw = Path(path).read_bytes()
    if len(raw) > 100_000:
        raise ValueError('Source annotations exceed 100,000 bytes')
    doc = json.loads(raw)
    if (not isinstance(doc, dict) or set(doc) != {'version', 'study_sha256', 'required_sources'}
            or type(doc['version']) is not int or doc['version'] != 1
            or doc['study_sha256'] != inputs['fingerprint']
            or not isinstance(doc['required_sources'], dict)):
        raise ValueError('Source annotations must bind the exact reply study')
    cases = {c['id']: c for c in inputs['document']['cases']}
    if set(doc['required_sources']) != set(cases):
        raise ValueError('Annotate every declared case exactly once')
    messages = {(m.source, m.id): m for m in inputs['messages']}
    if len(messages) != len(inputs['messages']):
        raise ValueError('Study source IDs must be unique')
    for case_id, refs in doc['required_sources'].items():
        if not isinstance(refs, list) or len(refs) > 20:
            raise ValueError('Use at most 20 required sources per reply')
        request = DraftRequest(**cases[case_id]['request'])
        pair, seen = (request.owner, request.contact), set()
        for ref in refs:
            if (not isinstance(ref, dict) or set(ref) != {'source', 'id'}
                    or any(not isinstance(v, str) or not v for v in ref.values())):
                raise ValueError('Required sources need exact source/id strings')
            key = ref['source'], ref['id']
            message = messages.get(key)
            if key in seen or message is None:
                raise ValueError('Required source is duplicate or unavailable')
            if ((message.author, message.recipient) not in (pair, pair[::-1])
                    or message.timestamp >= request.before):
                raise ValueError('Required source crosses the contact/time boundary')
            seen.add(key)
    return dict(document=doc, fingerprint=hashlib.sha256(raw).hexdigest())


def coverage(inputs, annotations, *, split='development'):
    if split not in ('development', 'evaluation', 'all'):
        raise ValueError('Choose a declared study split')
    store = Store()
    try:
        store.ingest(inputs['messages'])
        engine = DraftEngine(store)
        rows = []
        for case in inputs['document']['cases']:
            if split != 'all' and case['split'] != split:
                continue
            request = DraftRequest(**case['request'])
            required = {(r['source'], r['id']) for r in annotations['document']['required_sources'][case['id']]}
            for mode in MODES:
                packet = engine.prepare(replace(request, mode=mode))
                found = {(e.provenance['source'], e.provenance['id']) for e in packet.evidence if e.kind == 'message'}
                missing = sorted(required-found)
                rows.append(dict(case_id=case['id'], mode=mode, required=sorted(required),
                    retrieved=sorted(found), missing=missing, packet_sha256=packet.fingerprint,
                    required_source_recall=len(required & found)/len(required) if required else None,
                    complete=not missing, no_required_sources=not required))
        if not rows:
            raise ValueError('The selected split has no cases')
        contextual = [r for r in rows if r['mode'] != 'generic' and not r['no_required_sources']]
        return dict(version=1, study_sha256=inputs['fingerprint'], annotations_sha256=annotations['fingerprint'],
            split=split, cases=rows, contextual_source_cases=len(contextual),
            complete_contextual_source_cases=sum(r['complete'] for r in contextual),
            contextual_macro_source_recall=sum(r['required_source_recall'] for r in contextual)/len(contextual) if contextual else None,
            limitation='Author-labeled required-source coverage only; extra sources are not scored as wrong. '
            'Generic mode intentionally omits evidence. Complete retrieval does not establish factual entailment, '
            'a useful reply, up-to-date facts, or style preference. No inference or sending.')
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('--split', choices=('development', 'evaluation', 'all'), default='development')
    args = parser.parse_args()
    try:
        inputs = load_study(args.manifest)
        report = coverage(inputs, load_annotations(args.annotations, inputs), split=args.split)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'Evidence audit failed: {exc}\n')
    print(json.dumps(report, indent=2))
    if report['complete_contextual_source_cases'] < report['contextual_source_cases']:
        parser.exit(1)


if __name__ == '__main__': main()
