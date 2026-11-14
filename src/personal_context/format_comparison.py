"""Compare Ollama's decoder constraint on synthetic development replies."""

import argparse
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

from .frozen_retrieval import digest, source_fingerprint
from .generation_format import PROMPT_VERSION, SCHEMA, parse_proposal, prompt_messages
from .live_generation import load_study, study
from .model_options import add_model_options, configured_provider
from .retrieval_options import description


FORMATS = ('schema', 'prompt_only')


class _DiagnosticProvider:
    def __init__(self, provider, response_format):
        self.provider = provider
        self.response_format = response_format
        self.prompt_hashes = []

    def describe(self):
        return self.provider.describe() | {'response_format': self.response_format}

    def generate(self, packet):
        messages = prompt_messages(packet)
        self.prompt_hashes.append(digest(messages))
        schema = SCHEMA if self.response_format == 'schema' else None
        return parse_proposal(self.provider._chat(messages, schema=schema))


def declare(inputs, provider):
    cases = inputs['document']['cases']
    if any(case['split'] != 'development' or not case['request'].get('current_message')
           or not case['request'].get('intent') for case in cases):
        raise ValueError('Format diagnostic requires development-only cases with both explicit task fields')
    if not provider.config.expected_digest:
        raise ValueError('Format diagnostic requires an exact installed model digest')
    return dict(version=1, kind='development_only_response_format',
                benchmark_sha256=inputs['fingerprint'],
                inputs_sha256=digest(dict(document=inputs['document'],
                                          messages=[asdict(message) for message in inputs['messages']])),
                source_sha256=source_fingerprint(),
                prompt_version=PROMPT_VERSION, configuration=deepcopy(provider.describe()),
                retrieval_configuration=description(1), response_formats=list(FORMATS))


def compare(inputs, provider, frozen):
    reports = {}
    for response_format in FORMATS:
        if frozen != declare(inputs, provider):
            raise ValueError('Format diagnostic source, inputs, prompt or provider differs from its declaration')
        diagnostic = _DiagnosticProvider(provider, response_format)
        report = study(inputs, diagnostic, split='development', neighbor_window=1)
        reports[response_format] = report | {'prompt_sha256': diagnostic.prompt_hashes}
    if frozen != declare(inputs, provider):
        raise ValueError('Format diagnostic changed during inference')

    constrained, prompt_only = (reports[name] for name in FORMATS)
    if constrained['prompt_sha256'] != prompt_only['prompt_sha256']:
        raise ValueError('Paired format requests differ in prompt messages')
    paired = []
    for left, right in zip(constrained['cases'], prompt_only['cases'], strict=True):
        fields = ('case_id', 'mode', 'retrieved_sources', 'provider_calls')
        if any(left[field] != right[field] for field in fields):
            raise ValueError('Paired format attempts differ in case, sources or model access')
        paired.append(dict(case_id=left['case_id'], mode=left['mode'],
                           schema_status=left['status'], prompt_only_status=right['status']))
    return dict(version=1, kind='development_only_response_format_results',
                declaration_sha256=digest(frozen), paired=paired, reports=reports,
                evaluation_cases_inspected=False, reply_quality_scored=False, sending_performed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--output', type=Path, help='Run a declared comparison and write a new report')
    add_model_options(parser)
    args = parser.parse_args()
    try:
        if not args.local_model or not args.expected_model_digest:
            raise ValueError('Use an explicit installed local model and expected digest')
        inputs = load_study(args.manifest)
        provider = configured_provider(args)
        if args.output is None:
            path, result = args.receipt, declare(inputs, provider)
        else:
            path = args.output
            if path.exists():
                raise ValueError('Choose a new output path for the format diagnostic')
            result = compare(inputs, provider, json.loads(args.receipt.read_text()))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as handle:
            handle.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
        print(path)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'Format diagnostic failed: {exc}\n')


if __name__ == '__main__':
    main()
