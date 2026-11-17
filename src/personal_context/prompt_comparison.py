"""Compare versioned prompts on fixed synthetic requests and evidence."""

from dataclasses import asdict

from .frozen_retrieval import digest, source_fingerprint
from .generation_format import PROMPTS, PROMPT_VERSION, TASK_PROMPT_VERSION, parse_proposal, prompt_messages
from .live_generation import study
from .retrieval_options import description


VERSIONS = (PROMPT_VERSION, TASK_PROMPT_VERSION)


class _PromptProvider:
    def __init__(self, provider, version):
        self.provider = provider
        self.version = version

    def describe(self):
        return self.provider.describe() | {'prompt_version': self.version, 'response_format': 'prompt_only'}

    def generate(self, packet):
        messages = prompt_messages(packet, version=self.version)
        return parse_proposal(self.provider._chat(messages, schema=None))


def declare(inputs, criteria, provider, *, split):
    cases = inputs['document']['cases']
    if split not in ('development', 'evaluation') or any(case['split'] != split for case in cases):
        raise ValueError('Use a manifest containing only the declared split')
    if any(not case['request'].get('intent') or not case['request'].get('current_message') for case in cases):
        raise ValueError('Prompt comparison requires an explicit task for every case')
    checks = criteria.get('cases')
    if (type(criteria.get('version')) is not int or criteria['version'] != 1
            or not isinstance(checks, dict) or checks.keys() != {case['id'] for case in cases}
            or any(not isinstance(items, dict) or not items
                   or any(not name.strip() or not isinstance(label, str) or not label.strip()
                          for name, label in items.items()) for items in checks.values())):
        raise ValueError('Task criteria must cover every declared case')
    if not provider.config.expected_digest:
        raise ValueError('Prompt comparison requires an exact local model digest')
    inputs_sha256 = digest(dict(document=inputs['document'],
                                messages=[asdict(message) for message in inputs['messages']]))
    return dict(version=1, kind='synthetic_reply_prompt_comparison', split=split,
                benchmark_sha256=inputs['fingerprint'], criteria_sha256=digest(criteria),
                inputs_sha256=inputs_sha256, source_sha256=source_fingerprint(),
                versions=list(VERSIONS), prompts_sha256={version: digest(PROMPTS[version]) for version in VERSIONS},
                configuration=provider.describe(), response_format='prompt_only', retrieval=description(1))


def compare(inputs, criteria, provider, receipt):
    split = receipt['split']
    if receipt != declare(inputs, criteria, provider, split=split):
        raise ValueError('Prompt comparison inputs, code or model differ from the declaration')
    reports = {}
    for version in receipt['versions']:
        reports[version] = study(inputs, _PromptProvider(provider, version), split=split, neighbor_window=1)
        if receipt != declare(inputs, criteria, provider, split=split):
            raise ValueError('Prompt comparison declaration changed during inference')

    fields = ('case_id', 'mode', 'packet_sha256', 'retrieved_sources', 'provider_calls')
    for baseline, variant in zip(*(report['cases'] for report in reports.values()), strict=True):
        if any(baseline[field] != variant[field] for field in fields):
            raise ValueError('Prompt arms must share the request, evidence and model access decisions')
    return dict(version=1, kind='synthetic_reply_prompt_comparison_results',
                declaration_sha256=digest(receipt), split=split, reports=reports)
