"""Prepare masked synthetic reply reviews and retain the original attempt counts."""

from collections import Counter
from random import Random

from .drafts import DraftRequest
from .frozen_retrieval import digest
from .live_generation import MODES


ATTEMPT_STATUSES = ('needs_review', 'provider_abstained', 'rejected', 'needs_history')


def _case_history(messages, request):
    participants = (request.owner, request.contact)
    eligible = (message for message in messages
                if (message.author, message.recipient) in (participants, participants[::-1])
                and message.timestamp < request.before)
    return [dict(source=message.source, id=message.id, timestamp=message.timestamp, body=message.body,
                 speaker='owner' if message.author == request.owner else 'contact')
            for message in sorted(eligible, key=lambda item: (item.timestamp, item.source, item.id))]


def prepare_reviews(inputs, study, criteria, *, seed):
    """Create a reviewer packet and a coordinator key from a fixed synthetic report."""
    if type(seed) is not int:
        raise ValueError('Use an integer shuffle seed')
    conditions = study.get('reports', {'study': study})
    if not isinstance(conditions, dict) or not 1 <= len(conditions) <= 8:
        raise ValueError('Use one to eight study conditions')
    splits = {report['split'] for report in conditions.values()}
    if splits not in ({'development'}, {'evaluation'}):
        raise ValueError('All conditions must use the same single split')
    split = splits.pop()
    cases = {case['id']: case for case in inputs['document']['cases'] if case['split'] == split}
    checks = criteria.get('cases')
    if type(criteria.get('version')) is not int or criteria['version'] != 1 or not cases or (
            not isinstance(checks, dict) or checks.keys() != cases.keys()):
        raise ValueError('Criteria must cover exactly the selected case IDs')

    reviewer_cases = {}
    for case_id, case in cases.items():
        items = checks[case_id]
        request = DraftRequest(**case['request'])
        if (not isinstance(items, dict) or not items
                or any(not key.strip() or not isinstance(value, str) or not value.strip()
                       for key, value in items.items())):
            raise ValueError('Each case needs named, nonempty task criteria')
        if not request.current_message or not request.intent:
            raise ValueError('Review cases require an incoming message and reply goal')
        reviewer_cases[case_id] = dict(case_id=case_id, current_message=request.current_message,
            intent=request.intent, criteria=items.copy(), history=_case_history(inputs['messages'], request),
            candidates=[])

    attempts = []
    wordings = {case_id: set() for case_id in cases}
    expected = {(case_id, mode) for case_id in cases for mode in MODES}
    for condition, report in sorted(conditions.items()):
        rows = report['cases']
        pairs = {(row['case_id'], row['mode']) for row in rows}
        if (report['kind'] != 'synthetic provider reply study'
                or report['benchmark_sha256'] != inputs['fingerprint']
                or report['attempts'] != len(expected) or len(rows) != len(expected) or pairs != expected
                or report['statuses'] != dict(Counter(row['status'] for row in rows))):
            raise ValueError('Study report must match the fixture and include every case and mode once')
        for row in rows:
            case_id, mode, status, wording = (row[field] for field in ('case_id', 'mode', 'status', 'draft_text'))
            if (row['split'] != split or status not in ATTEMPT_STATUSES or not isinstance(wording, str)
                    or (status == 'needs_review' and not 1 <= len(wording.strip()) <= 6000)
                    or (status != 'needs_review' and wording != '')):
                raise ValueError('Invalid attempt status or wording')
            if status == 'needs_review':
                wordings[case_id].add(wording)
            attempts.append((condition, case_id, mode, status, wording))

    ids = {}
    shuffle = Random(seed)
    for case_id, case in reviewer_cases.items():
        ordered = sorted(wordings[case_id])
        shuffle.shuffle(ordered)
        for wording in ordered:
            candidate_id = f'reply-{len(ids)+1:03}'
            ids[case_id, wording] = candidate_id
            case['candidates'].append(dict(id=candidate_id, wording=wording))
    packet = dict(version=1, split=split, cases=list(reviewer_cases.values()))
    key = dict(packet_sha256=digest(packet), study_sha256=digest(study),
               attempts=[dict(condition=condition, case_id=case_id, mode=mode, status=status,
                              candidate_id=ids.get((case_id, wording)))
                         for condition, case_id, mode, status, wording in attempts])
    return packet, key
