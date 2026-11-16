"""Export or score a local review packet for a synthetic reply study."""

import argparse
import json
from pathlib import Path

from .live_generation import load_study
from .reply_quality import prepare_reviews, summarize_reviews


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'score'))
    parser.add_argument('manifest', type=Path)
    parser.add_argument('study', type=Path)
    parser.add_argument('criteria', type=Path)
    parser.add_argument('--seed', type=int, required=True, help='Use the same coordinator seed for export and score')
    parser.add_argument('--ratings', type=Path, help='Completed rating template for score')
    parser.add_argument('--output', type=Path, required=True, help='New JSON output file')
    args = parser.parse_args(argv)
    try:
        if (args.action == 'score') != (args.ratings is not None):
            raise ValueError('Provide --ratings for score only')
        inputs = load_study(args.manifest)
        study = json.loads(args.study.read_text())
        criteria = json.loads(args.criteria.read_text())
        packet, key = prepare_reviews(inputs, study, criteria, seed=args.seed)
        if args.action == 'export':
            result = dict(packet=packet, rating_template=dict(
                version=1, packet_sha256=key['packet_sha256'], reviewer_kind=None, prior_exposure=None,
                ratings={candidate['id']: dict(support=None, completed=[], note='')
                         for case in packet['cases'] for candidate in case['candidates']}))
        else:
            ratings = json.loads(args.ratings.read_text())
            result = summarize_reviews(packet, key, ratings)
        payload = json.dumps(result, indent=2, allow_nan=False, ensure_ascii=False) + '\n'
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as handle:
            handle.write(payload)
        print(args.output)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        parser.exit(2, f'Reply review failed: {exc}\n')


if __name__ == '__main__':
    main()
