"""Export or score a local review packet for a synthetic reply study."""

import argparse
import json
from pathlib import Path

from .live_generation import load_study
from .reply_quality import compare_reviews, prepare_reviews, review_progress, summarize_reviews
from .reply_review_form import rating_template, render_review_form


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'score', 'form', 'progress', 'compare'))
    parser.add_argument('manifest', type=Path)
    parser.add_argument('study', type=Path)
    parser.add_argument('criteria', type=Path)
    parser.add_argument('--seed', type=int, required=True, help='Use the same coordinator seed for export and score')
    parser.add_argument('--ratings', type=Path, help='Ratings file for score, progress or compare')
    parser.add_argument('--second-ratings', type=Path, help='Second completed file for compare only')
    parser.add_argument('--output', type=Path, required=True, help='New output file (HTML for form, JSON otherwise)')
    args = parser.parse_args(argv)
    try:
        if (args.action in ('score', 'progress', 'compare')) != (args.ratings is not None):
            raise ValueError('Provide --ratings for score, progress or compare only')
        if (args.action == 'compare') != (args.second_ratings is not None):
            raise ValueError('Provide --second-ratings for compare only')
        inputs = load_study(args.manifest)
        study = json.loads(args.study.read_text())
        criteria = json.loads(args.criteria.read_text())
        packet, key = prepare_reviews(inputs, study, criteria, seed=args.seed)
        if args.action == 'export':
            result = dict(packet=packet, rating_template=rating_template(packet))
        elif args.action == 'form':
            result = None
        else:
            ratings = json.loads(args.ratings.read_text())
            if args.action == 'compare':
                result = compare_reviews(packet, key, ratings, json.loads(args.second_ratings.read_text()))
            else:
                result = (review_progress if args.action == 'progress' else summarize_reviews)(packet, key, ratings)
        payload = (render_review_form(packet, key) if args.action == 'form' else
                   json.dumps(result, indent=2, allow_nan=False, ensure_ascii=False) + '\n')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as handle:
            handle.write(payload)
        print(args.output)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        parser.exit(2, f'Reply review failed: {exc}\n')


if __name__ == '__main__':
    main()
