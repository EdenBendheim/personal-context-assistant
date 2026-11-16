# Rating synthetic replies

Use the incoming message, requested reply goal and shared case history. Rate
each distinct wording once per case. For factual support, inspect every claim,
including confirmation, completed actions and factual assumptions made in
questions. Cite the shared history in your note when a claim is disputed.
Judge what the wording says and implies.

| Support rating | Meaning |
| --- | --- |
| `supported` | The history supports all claims, or the reply makes no factual claims. |
| `unsupported` | At least one claim exceeds or contradicts the history. |
| `uncertain` | The available wording or context leaves the reviewer unsure about support. |

Mark every completed task criterion in the rating. Count a task as complete
only when the reply meets all its criteria. A reply can complete a task while
making an unsupported claim, or stay factual while missing the requested
action. Count a reply as passing both checks only when its support rating is
`supported` and all its task criteria are met.

The review packet gives every candidate for a case the same history before
its cutoff. This measures whether the wording is supported by shared case
history. The original study separately records whether each system supplied
literal citations to its retrieved evidence. Counts retain every original
attempt, including abstentions, rejections and skipped calls. Exact
duplicate wording within a case receives one rating and counts once per
original attempt in the decoded totals.

Keep the decoder or model identity key with the study coordinator until
ratings are locked. Keep a note with each rating. Record whether the ratings
came from a human or an assistant and whether that reviewer had previous
exposure to the outputs. A short development audit gives examples for
calibration. Independent and human ratings need their own review passes.

## Export and score

Use this command from the repository root to export the archived November 13
study. Use a coordinator seed and keep it with the study inputs until review
is complete.

```sh
PYTHONPATH=src python3 -m personal_context.reply_quality_cli export \
  examples/reply_intent_development/manifest.json \
  experiments/reply-union-2026-11-13/results.json \
  examples/reply_intent_development/criteria.json \
  --seed 29 --output runs/reply-review.json
```

Give the reviewer the exported file and this rubric. Copy its
`rating_template` into a separate ratings JSON, then fill in `reviewer_kind`
(`human` or `assistant`), `prior_exposure` (a boolean), and every candidate
entry. List the IDs of completed criteria in `completed` and describe the
judgment in `note`.

Score with the same manifest, study, criteria and seed.

```sh
PYTHONPATH=src python3 -m personal_context.reply_quality_cli score \
  examples/reply_intent_development/manifest.json \
  experiments/reply-union-2026-11-13/results.json \
  examples/reply_intent_development/criteria.json \
  --seed 29 --ratings runs/reply-ratings.json --output runs/reply-scores.json
```

The score command reconstructs the original condition mapping locally. It
requires the packet fingerprint and a complete set of ratings. Each output
must use a fresh path. The documented seed demonstrates reproduction on
public fixtures. For a masked review, share only the export and rubric.
