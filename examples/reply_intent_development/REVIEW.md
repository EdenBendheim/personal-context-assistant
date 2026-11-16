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
