# Scoring archived synthetic replies

All three decoder settings scored zero replies that met every task criterion
and had factual support. The November 13 study supplied 27 attempts from
three invented conversations. Nine attempts yielded drafts for review, with
six distinct wordings. This assessment reuses those replies.

| Decoder | Attempts | Drafts reviewed | Supported | Unsupported | Uncertain | Task complete |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Union schema | 9 | 1 | 0 | 1 | 0 | 0 |
| Flat schema | 9 | 1 | 0 | 1 | 0 | 0 |
| Prompt only | 9 | 7 | 2 | 4 | 1 | 0 |

The assistant rated each distinct wording against the shared case history and
[task criteria](../examples/reply_intent_development/criteria.json). The
packet hid the decoder labels during rating, and the same assistant had
already seen the original outputs. The ratings are an exposed development
audit. Human review and agreement between raters remain open.

The workshop reply that restates the time and room earns factual support but
omits thanks. The export reply says the owner saw the correction, which the
history does not establish. It asks the recipient to send the file. The goal
asks where to find it. The ticket reply that names the right branch asks what
the recipient has already run. The goal asks which test the owner should run.
These distinctions explain why valid JSON and literal citations alone do
not establish that a reply is ready to use.

The score command verifies the packet fingerprint before mapping ratings back
to the original attempts, including abstentions and rejections. Exact duplicate
wordings share one rating. The CLI works from the archived report with no model
calls, and production review continues to require human approval.
[Rubric and replay commands](../examples/reply_intent_development/REVIEW.md) ·
[Ratings](reply-quality-2026-11-15/ratings.json) ·
[Decoded scores](reply-quality-2026-11-15/scores.json)
