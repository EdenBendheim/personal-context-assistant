"""Frozen development-only topic-versus-explicit-task generation diagnostic."""

import argparse
from copy import deepcopy
import json
from pathlib import Path

from .frozen_retrieval import digest, source_fingerprint
from .generation_format import PROMPT_VERSION
from .live_generation import load_study, study
from .model_options import add_model_options, configured_provider
from .retrieval_options import description


def variants(inputs):
    cases = inputs['document']['cases']
    if (any(case['split'] != 'development' for case in cases)
            or any(not case['request'].get('current_message') or not case['request'].get('intent') for case in cases)):
        raise ValueError('Intent diagnostic requires development-only cases with both explicit task fields')
    result = {}
    for name in ('topic_only', 'explicit_task'):
        selected = deepcopy(inputs)
        if name == 'topic_only':
            for case in selected['document']['cases']:
                for field in ('current_message', 'intent'):
                    case['request'].pop(field)
        selected['fingerprint'] = digest(dict(original=inputs['fingerprint'], variant=name,
                                              requests=[case['request'] for case in selected['document']['cases']]))
        result[name] = selected
    return result


def declare(inputs, provider):
    prepared = variants(inputs)
    return dict(version=1, kind='development_only_reply_intent', benchmark_sha256=inputs['fingerprint'],
        variant_sha256={key: value['fingerprint'] for key, value in prepared.items()},
        source_sha256=source_fingerprint(), prompt_version=PROMPT_VERSION,
        configuration=deepcopy(provider.describe()), retrieval_configuration=description(1),
        rule='Same prompt/model/history; vary only current_message and intent. Development only, no setting selection.')


def compare(inputs, provider, frozen):
    if frozen != declare(inputs, provider):
        raise ValueError('Intent diagnostic source, inputs, prompt or provider differs from its frozen declaration')
    reports = {}
    for name, selected in variants(inputs).items():
        if frozen != declare(inputs, provider):
            raise ValueError('Intent diagnostic changed before model access')
        reports[name] = study(selected, provider, split='development', neighbor_window=1)
    if frozen != declare(inputs, provider):
        raise ValueError('Intent diagnostic changed during inference')
    paired = []
    for old, new in zip(reports['topic_only']['cases'], reports['explicit_task']['cases'], strict=True):
        if ((old['case_id'], old['mode'], old['retrieved_sources']) !=
                (new['case_id'], new['mode'], new['retrieved_sources'])):
            raise ValueError('Paired intent cases differ in contact, mode or retrieved sources')
        paired.append(dict(case_id=old['case_id'], mode=old['mode'], topic_only_status=old['status'],
            explicit_task_status=new['status'], topic_only_reason=old.get('abstain_reason'),
            explicit_task_reason=new.get('abstain_reason')))
    return dict(version=1, kind='development_only_reply_intent_results', declaration_sha256=digest(frozen),
        reports=reports, paired=paired, evaluation_cases_inspected=False, reply_quality_scored=False,
        sending_performed=False, limitation='Small authored development diagnostic. A changed draft/abstention count '
        'does not establish factual support, usefulness, style or held-out improvement. Human review remains required.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('declare', 'run'))
    parser.add_argument('manifest', type=Path)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--output', type=Path)
    add_model_options(parser)
    args = parser.parse_args()
    try:
        inputs = load_study(args.manifest)
        if not args.local_model or not args.expected_model_digest:
            raise ValueError('Use an explicit installed local model and expected digest')
        provider = configured_provider(args)
        if args.action == 'declare':
            if args.output is not None:
                raise ValueError('Declaration writes only its exclusive-create receipt')
            frozen = declare(inputs, provider)
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            with args.receipt.open('x') as handle:
                handle.write(json.dumps(frozen, indent=2, allow_nan=False)+'\n')
            print(json.dumps(dict(declared=True, declaration_sha256=digest(frozen))))
        else:
            if args.output is None or args.output.exists():
                raise ValueError('Choose a new output path for the intent diagnostic')
            result = compare(inputs, provider, json.loads(args.receipt.read_text()))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x') as handle:
                handle.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
            print(json.dumps(dict(completed=True, variants={key: value['statuses'] for key, value in result['reports'].items()})))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'Intent diagnostic failed: {exc}\n')


if __name__ == '__main__':
    main()
