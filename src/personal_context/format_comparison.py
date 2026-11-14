"""Compare Ollama's decoder constraint on synthetic development replies."""

import argparse
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

from .frozen_retrieval import digest, source_fingerprint
from .generation_format import FLAT_SCHEMA, PROMPT_VERSION, SCHEMA, parse_proposal, prompt_messages
from .live_generation import load_study, study
from .model_options import add_model_options, configured_provider
from .retrieval_options import description


DECODER_SCHEMAS = {'schema': SCHEMA, 'flat_schema': FLAT_SCHEMA, 'prompt_only': None}
COMPARISONS = {'constraint': ('schema', 'prompt_only'), 'union': ('schema', 'flat_schema', 'prompt_only')}


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
        schema = DECODER_SCHEMAS[self.response_format]
        return parse_proposal(self.provider._chat(messages, schema=schema))


def declare(inputs, provider, *, comparison='constraint'):
    if comparison not in COMPARISONS:
        raise ValueError('Choose a declared format comparison')
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
                retrieval_configuration=description(1), comparison=comparison,
                response_formats=list(COMPARISONS[comparison]),
                decoder_schema_sha256={name: digest(DECODER_SCHEMAS[name]) for name in COMPARISONS[comparison]})


def compare(inputs, provider, frozen, *, comparison='constraint'):
    current = declare(inputs, provider, comparison=comparison)
    if frozen != current:
        raise ValueError('Format diagnostic source, inputs, prompt or provider differs from its declaration')
    reports = {}
    for response_format in current['response_formats']:
        diagnostic = _DiagnosticProvider(provider, response_format)
        report = study(inputs, diagnostic, split='development', neighbor_window=1)
        reports[response_format] = report | {'prompt_sha256': diagnostic.prompt_hashes}
        if frozen != declare(inputs, provider, comparison=comparison):
            raise ValueError('Format diagnostic changed during inference')

    reference = reports['schema']
    if any(report['prompt_sha256'] != reference['prompt_sha256'] for report in reports.values()):
        raise ValueError('Matched format requests differ in prompt messages')
    paired = []
    for matched in zip(*(report['cases'] for report in reports.values()), strict=True):
        reference_row = matched[0]
        fields = ('case_id', 'mode', 'retrieved_sources', 'provider_calls')
        if any(row[field] != reference_row[field] for row in matched[1:] for field in fields):
            raise ValueError('Matched format attempts differ in case, sources or model access')
        statuses = {f'{name}_status': row['status'] for name, row in zip(reports, matched, strict=True)}
        paired.append(dict(case_id=reference_row['case_id'], mode=reference_row['mode'], **statuses))
    return dict(version=1, kind='development_only_response_format_results',
                declaration_sha256=digest(frozen), paired=paired, reports=reports,
                evaluation_cases_inspected=False, reply_quality_scored=False, sending_performed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--output', type=Path, help='Run a declared comparison and write a new report')
    parser.add_argument('--comparison', choices=COMPARISONS, default='constraint')
    add_model_options(parser)
    args = parser.parse_args()
    try:
        if not args.local_model or not args.expected_model_digest:
            raise ValueError('Use an explicit installed local model and expected digest')
        inputs = load_study(args.manifest)
        provider = configured_provider(args)
        if args.output is None:
            path, result = args.receipt, declare(inputs, provider, comparison=args.comparison)
        else:
            path = args.output
            if path.exists():
                raise ValueError('Choose a new output path for the format diagnostic')
            result = compare(inputs, provider, json.loads(args.receipt.read_text()), comparison=args.comparison)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as handle:
            handle.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
        print(path)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'Format diagnostic failed: {exc}\n')


if __name__ == '__main__':
    main()
