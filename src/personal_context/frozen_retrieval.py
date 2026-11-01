"""Select on development cases, then refuse evaluation against a changed setup."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from .embedding_cli import add_embedding_arguments, provider_from_arguments
from .evaluation import load_benchmark
from .retrieval_comparison import compare_retrieval

THRESHOLDS = (.2, .4, .6, .8)
RULE = 'Zero boundary violations; maximize harmonic mean of macro precision/recall, then precision, then threshold'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def source_fingerprint():
    root = Path(__file__).parent
    return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.py'))})


def _rank(report):
    metrics = report['embedding']
    if metrics['boundary_violations']:
        return None
    precision, recall = metrics['macro_precision'], metrics['macro_recall']
    if any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1 for x in (precision, recall)):
        return None
    harmonic = 2*precision*recall/(precision+recall) if precision+recall else 0.
    return harmonic, precision, report['embedding_configuration']['min_score']


def select_development(benchmark, provider, *, thresholds=THRESHOLDS, max_candidates=128):
    thresholds = tuple(thresholds)
    if (not 1 <= len(thresholds) <= 8 or len(set(thresholds)) != len(thresholds)
            or any(type(t) not in (int, float) or not math.isfinite(t) or not -1 <= t <= 1 for t in thresholds)):
        raise ValueError('Use one to eight unique finite cosine thresholds')
    configuration = deepcopy(provider.describe())
    reports = [compare_retrieval(benchmark, provider, split='development', min_score=t,
                                max_candidates=max_candidates) for t in thresholds]
    eligible = [r for r in reports if _rank(r) is not None]
    if not eligible:
        raise ValueError('No development candidate has valid metrics and zero boundary violations')
    selected = max(eligible, key=_rank)
    if configuration != provider.describe():
        raise ValueError('Provider configuration changed during threshold selection')
    frozen = dict(version=1, kind='development-frozen synthetic retrieval', selection_rule=RULE,
        benchmark_sha256=benchmark.fingerprint, source_sha256=source_fingerprint(),
        provider_configuration=configuration, thresholds=list(thresholds), max_candidates=max_candidates,
        selected_threshold=selected['embedding_configuration']['min_score'], development=reports,
        evaluation_inspected=False)
    return dict(frozen, freeze_sha256=digest(frozen))


def evaluate_frozen(benchmark, provider, frozen):
    frozen = deepcopy(frozen)
    receipt = frozen.pop('freeze_sha256', None)
    if receipt != digest(frozen) or frozen.get('version') != 1 or frozen.get('kind') != 'development-frozen synthetic retrieval':
        raise ValueError('Invalid development freeze receipt')
    if (frozen['benchmark_sha256'] != benchmark.fingerprint or frozen['source_sha256'] != source_fingerprint()
            or frozen['provider_configuration'] != provider.describe()):
        raise ValueError('Benchmark, source code or provider configuration changed after development freeze')
    if frozen['evaluation_inspected'] is not False or frozen['selection_rule'] != RULE:
        raise ValueError('Invalid development selection protocol')
    report = compare_retrieval(benchmark, provider, split='evaluation', min_score=frozen['selected_threshold'],
                              max_candidates=frozen['max_candidates'])
    return dict(report, development_freeze_sha256=receipt, source_sha256=frozen['source_sha256'],
                threshold_selected_on='development', limitation=report['limitation']+
                '; small previously established synthetic cases, not a fresh real-user holdout')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('select', 'evaluate'))
    parser.add_argument('manifest', type=Path)
    parser.add_argument('freeze', type=Path)
    add_embedding_arguments(parser)
    args = parser.parse_args()
    try:
        if not args.expected_model_digest:
            raise ValueError('Frozen real-model comparison requires an expected model digest')
        benchmark, provider = load_benchmark(args.manifest), provider_from_arguments(args)
        if args.stage == 'select':
            result = select_development(benchmark, provider, max_candidates=args.max_candidates)
            # Do not replace an existing development decision after observing evaluation.
            with args.freeze.open('x') as stream:
                stream.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
        else:
            if args.freeze.stat().st_size > 2_000_000:
                raise ValueError('Development freeze exceeds two megabytes')
            result = evaluate_frozen(benchmark, provider, json.loads(args.freeze.read_text()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f'Frozen retrieval failed: {exc}\n')
    print(json.dumps(result, indent=2, allow_nan=False))
    if args.stage == 'evaluate' and not result['passed']:
        parser.exit(1)


if __name__ == '__main__': main()
